"""ViewSet для работы с моделью track."""

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from common.access import managed_artist_q
from common.permissions import (
    CanCreateArtistContent,
    IsArtistOrLabel,
    IsStoreObjectManager,
)

from .mixins import (
    ProductActionMixin,
    SoftDeleteMixin,
    TrackReadQuerysetMixin,
)
from store.filters import TrackFilter
from store.models import Album, ReleaseTrack
from store.schema import track_reorder_schema, track_schema
from store.serializers import (
    TrackPlacementCreateSerializer,
    TrackReadDetailSerializer,
    TrackReadSerializer,
    TrackReorderSerializer,
    TrackWriteSerializer,
)
from store.services import TrackService, get_track_sales_stats, reorder_objects
from store.services.album_archive import AlbumArchiveScheduler
from store.services.album_publication import unpublish_if_empty


class TrackOrderingFilter(filters.OrderingFilter):
    """Сохраняет публичные имена полей сортировки треков."""

    ordering_aliases = {
        'name': 'recording__name',
    }

    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)

        if not ordering:
            return ordering

        result = []

        for field in ordering:
            descending = field.startswith('-')
            field_name = field.removeprefix('-')
            internal_name = self.ordering_aliases.get(
                field_name,
                field_name,
            )

            result.append(
                f'-{internal_name}' if descending else internal_name,
            )

        return result


@track_schema
class TrackViewSet(
    TrackReadQuerysetMixin,
    ProductActionMixin,
    SoftDeleteMixin,
    viewsets.ModelViewSet,
):
    """API для работы с треками."""

    queryset = ReleaseTrack.objects.all()
    permission_classes = (IsArtistOrLabel, IsStoreObjectManager)
    http_method_names = ('get', 'post', 'patch', 'delete')
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        TrackOrderingFilter,
    )
    filterset_class = TrackFilter
    search_fields = ('recording__name',)
    ordering_fields = ('name', 'position')
    ordering = ('release_id', 'position', 'id')

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return TrackWriteSerializer
        if self.action == 'retrieve':
            return TrackReadDetailSerializer
        return TrackReadSerializer

    def get_queryset(self):
        """Возвращает треки, доступные текущему пользователю."""
        user = self.request.user
        queryset = super().get_queryset()

        if not user.is_authenticated:
            return queryset.none()

        queryset = queryset.filter(
            Q(is_active=True)
            & managed_artist_q(user, prefix='release__artist'),
        )
        return self.get_track_read_queryset(
            action=self.action,
            queryset=queryset,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = TrackReadDetailSerializer(
            instance,
            context=self.get_serializer_context(),
        )
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        read_serializer = TrackReadDetailSerializer(
            instance,
            context=self.get_serializer_context(),
        )
        return Response(read_serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Удаляет трек и снимает пустой альбом с публикации."""
        track = self.get_object()
        release = track.release
        sales = get_track_sales_stats(track)

        if sales.total_sales:
            return Response(
                {
                    'detail': (
                        'Нельзя удалить трек с историей приобретения. '
                        f'Трек куплен отдельно: {sales.direct_sales} раз; '
                        f'в составе релиза: {sales.release_sales} раз. '
                        'Снимите текущий релиз с продажи и создайте новый '
                        'без этого трека.'
                    ),
                },
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            response = super().destroy(request, *args, **kwargs)
            unpublish_if_empty(release)

            transaction.on_commit(
                lambda: AlbumArchiveScheduler.schedule_by_id(release.pk),
            )

        return response

    @track_reorder_schema
    @action(
        detail=False,
        methods=['patch'],
        url_path='reorder',
        pagination_class=None,
    )
    def reorder(self, request):
        """Задаёт порядок треков альбома за один запрос."""
        serializer = TrackReorderSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        release = serializer.validated_data['album']

        reorder_objects(
            ReleaseTrack.objects.filter(release=release, is_active=True),
            serializer.validated_data['track_ids'],
            'track_ids',
        )
        transaction.on_commit(
            lambda: AlbumArchiveScheduler.schedule_by_id(release.pk),
        )

        tracks = (
            self
            .get_queryset()
            .filter(
                release=release,
            )
            .order_by('position')
        )

        return Response(
            TrackReadSerializer(
                tracks,
                many=True,
                context=self.get_serializer_context(),
            ).data,
        )


class AlbumTrackCreateView(APIView):
    """Размещает существующую запись в релизе."""

    permission_classes = (CanCreateArtistContent,)

    def post(self, request, album_id):
        album = get_object_or_404(Album, pk=album_id)

        serializer = TrackPlacementCreateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        track = TrackService.add_recording(
            release=album,
            recording=data['recording'],
            user=request.user,
            price=data.get('price'),
            allow_overpay=data['allow_overpay'],
        )

        return Response(
            TrackReadDetailSerializer(
                track,
                context={'request': request},
            ).data,
            status=status.HTTP_201_CREATED,
        )
