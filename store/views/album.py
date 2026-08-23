"""ViewSet для управления альбомами."""

from django.db.models import Prefetch, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from common.access import managed_artist_q
from common.permissions import IsArtistOrLabel, IsStoreObjectManager

from .mixins import ProductActionMixin, SoftDeleteMixin
from store.constants import CHAR_PRESET_DIGITAL
from store.filters import AlbumFilter
from store.models import Album, ProductVariant
from store.schema import album_schema
from store.serializers import (
    AlbumReadDetailSerializer,
    AlbumReadSerializer,
    AlbumWriteSerializer,
)


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
    permission_classes = (IsArtistOrLabel, IsStoreObjectManager)
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

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return AlbumWriteSerializer
        if self.action == 'retrieve':
            return AlbumReadDetailSerializer
        return AlbumReadSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        if not user.is_authenticated:
            return queryset.none()

        queryset = queryset.filter(
            Q(is_active=True) & managed_artist_q(user),
        )

        digital_variants_prefetch = Prefetch(
            'product__variants',
            queryset=ProductVariant.objects.filter(
                is_active=True,
                property_value=CHAR_PRESET_DIGITAL,
            ),
            to_attr='digital_variants',
        )

        if self.action == 'list':
            queryset = queryset.select_related(
                'product',
                'artist',
            ).prefetch_related(
                digital_variants_prefetch,
            )
        elif self.action == 'retrieve':
            queryset = queryset.select_related(
                'product',
                'genre',
                'artist',
                'artist__label',
            ).prefetch_related(
                digital_variants_prefetch,
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
