"""ViewSet для работы с моделью track."""

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from common.access import managed_artist_q
from common.permissions import IsArtistOrLabel, IsStoreObjectManager

from .mixins import (
    ProductActionMixin,
    SoftDeleteMixin,
    TrackReadQuerysetMixin,
)
from store.filters import TrackFilter
from store.models import Track
from store.schema import track_schema
from store.serializers import (
    TrackReadDetailSerializer,
    TrackReadSerializer,
    TrackWriteSerializer,
)


@track_schema
class TrackViewSet(
    TrackReadQuerysetMixin,
    ProductActionMixin,
    SoftDeleteMixin,
    viewsets.ModelViewSet,
):
    """API для работы с треками."""

    queryset = Track.objects.all()
    permission_classes = (IsArtistOrLabel, IsStoreObjectManager)
    http_method_names = ('get', 'post', 'patch', 'delete')
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    )
    filterset_class = TrackFilter
    search_fields = ('name',)
    ordering_fields = ('name', 'position')
    ordering = ('album', 'position')

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
            Q(is_active=True) & managed_artist_q(user, prefix='album__artist'),
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
        album = track.album

        response = super().destroy(request, *args, **kwargs)

        has_uploaded_track = (
            album.tracks
            .filter(
                audio_file__isnull=False,
                is_active=True,
            )
            .exclude(audio_file='')
            .exists()
        )

        if album.is_published and not has_uploaded_track:
            album.is_published = False
            album.save(update_fields=('is_published',))

        return response
