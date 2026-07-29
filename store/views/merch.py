from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.access import managed_artist_q
from common.permissions import IsArtistOrLabel, IsStoreObjectManager

from store.filters.merch import MerchFilter
from store.models import Image, Merch
from store.schema.merch import merch_schema
from store.schema.merch_images import add_image_schema, image_detail_schema
from store.serializers import (
    ImageSerializer,
    MerchDetailSerializer,
    MerchReadSerializer,
    MerchWriteSerializer,
)
from store.services import MerchImageService
from store.views.mixins import ProductActionMixin, SoftDeleteMixin


@merch_schema
class MerchViewSet(ProductActionMixin, SoftDeleteMixin, viewsets.ModelViewSet):
    """API для работы с мерчем.

    Особенности:
    - Обеспечение коммерческой обвязки через ProductActionMixin.
    - Мягкое удаление объектов через SoftDeleteMixin
      для сохранения связи с заказами.
    - Динамическое разграничение прав доступа
      и видимости объектов на уровне QuerySet.

    При create/update:
    * Данные мерча сохраняются через валидацию сериализатора.
    * Далее ProductActionMixin:
        - Вызывает ProductService.ensure_commerce(), который гарантирует
          наличие связанного Product и ProductVariant,
          а также управляет вариантами.
        - Синхронизирует коммерческие поля (price, allow_overpay).
    """

    queryset = Merch.objects.all()
    permission_classes = (IsArtistOrLabel, IsStoreObjectManager)
    http_method_names = ('get', 'post', 'patch', 'delete')
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    )
    filterset_class = MerchFilter
    search_fields = ('name', 'description')
    ordering_fields = ('name', 'created_at')
    ordering = ('name',)

    def get_serializer_class(self):
        if self.action == 'list':
            return MerchReadSerializer
        if self.action == 'retrieve':
            return MerchDetailSerializer
        return MerchWriteSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        if not user.is_authenticated:
            return queryset.none()

        queryset = queryset.filter(
            Q(is_active=True) & managed_artist_q(user),
        )
        if self.action == 'list':
            queryset = queryset.select_related(
                'product',
            ).prefetch_related(
                'images_merch',
            )
        elif self.action == 'retrieve':
            queryset = queryset.select_related(
                'product',
                'kind',
                'album',
                'artist',
                'payout_recipient',
            ).prefetch_related(
                'images_merch',
                'product__variants',
            )
        return queryset

    @add_image_schema
    @action(detail=True, methods=['post'], url_path='images')
    def add_image(self, request, pk=None):
        """Добавляет изображение мерча."""
        merch = self.get_object()
        serializer = ImageSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        image = MerchImageService.create_image(
            merch=merch,
            validated_data=serializer.validated_data,
        )

        return Response(
            ImageSerializer(
                image,
                context={'request': request},
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @image_detail_schema
    @action(
        detail=True,
        methods=['patch', 'delete'],
        url_path='images/(?P<image_id>[0-9]+)',
    )
    def image_detail(self, request, pk=None, image_id=None):
        """Обновляет или удаляет изображение мерча."""
        merch = self.get_object()
        image = get_object_or_404(
            Image,
            id=image_id,
            merch=merch,
        )

        if request.method == 'DELETE':
            MerchImageService.delete_image(image=image)
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = ImageSerializer(
            image,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        image = MerchImageService.update_image(
            image=image,
            validated_data=serializer.validated_data,
        )

        return Response(
            ImageSerializer(
                image,
                context={'request': request},
            ).data,
        )
