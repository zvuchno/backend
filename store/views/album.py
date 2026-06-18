"""ViewSet для управления альбомами."""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from common.permissions import IsArtist, IsStoreObjectOwnerOrReadOnly

from .mixins import ProductActionMixin, SoftDeleteMixin
from store.filters import AlbumFilter
from store.models import Album
from store.schema import album_schema
from store.serializers import (
    AlbumReadDetailSerializer,
    AlbumReadSerializer,
    AlbumWriteSerializer,
)
from store.services.album_archive import AlbumArchiveScheduler


@album_schema
class AlbumViewSet(ProductActionMixin, SoftDeleteMixin, viewsets.ModelViewSet):
    """API для работы с альбомами.

    Особенности:
    - Обеспечение коммерческой обвязки через ProductActionMixin.
    - Поддержка правил доступа и видимости объектов.

    При create/update:
    - данные альбома сохраняются через сериализатор
    - далее ProductActionMixin:
        * вызывает ProductService.ensure_commerce(), который гарантирует
        наличие связанного Product и ProductVariant
        * синхронизирует коммерческие поля (price, allow_overpay)
    """

    queryset = Album.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    )
    filterset_class = AlbumFilter
    search_fields = ('name', 'genre__name')
    ordering_fields = ('name', 'created_at', 'release_date')
    ordering = ('-created_at', 'name')

    def get_permissions(self):
        if self.action == 'create':
            return (IsArtist(),)
        return (IsStoreObjectOwnerOrReadOnly(),)

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return AlbumWriteSerializer
        if self.action == 'retrieve':
            return AlbumReadDetailSerializer
        return AlbumReadSerializer

    def get_queryset(self):
        # Вызываем базовый QS с фильтрацией
        queryset = (
            super()
            .get_queryset()
            .visible_for(
                user=self.request.user,
                action=self.action,
            )
        )
        if self.action in ('list', 'retrieve'):
            queryset = queryset.select_related(
                'product',
                'genre',
                'owner__artist_profile',
            )
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = AlbumReadDetailSerializer(
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
        read_serializer = AlbumReadDetailSerializer(
            instance,
            context=self.get_serializer_context(),
        )
        return Response(read_serializer.data)

    def perform_create(self, serializer):
        super().perform_create(serializer)

        AlbumArchiveScheduler.schedule(
            serializer.instance,
        )

    def perform_update(self, serializer):
        super().perform_update(serializer)

        AlbumArchiveScheduler.schedule(
            serializer.instance,
        )
