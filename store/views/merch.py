from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import IsStoreObjectOwnerOrReadOnly

from store.filters.merch import MerchFilter
from store.models import Image, Merch, ProductVariant
from store.schema.merch import merch_schema
from store.serializers import (
    ImageSerializer,
    MerchDetailSerializer,
    MerchReadSerializer,
    MerchWriteSerializer,
    VariantReadSerializer,
    VariantWriteSerializer,
)
from store.views.mixins import ProductActionMixin


@merch_schema
class MerchViewSet(ProductActionMixin, viewsets.ModelViewSet):
    """API для работы с мерчем."""

    permission_classes = (IsStoreObjectOwnerOrReadOnly,)
    http_method_names = ('get', 'post', 'patch', 'delete')
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter
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
        return (
            Merch.objects
            .visible_for(self.request.user, self.action)
            .select_related('product', 'kind', 'album', 'owner')
            .prefetch_related(
                'images_merch',
                'product__variants'
            )
        )

    @action(detail=True, methods=['get'], url_path='variants')
    def list_variants(self, request, pk=None):
        merch = self.get_object()
        product = getattr(merch, 'product', None)
        if not product:
            return Response([])
        variants = product.variants.all().order_by('id')
        serializer = VariantReadSerializer(variants, many=True)
        return Response(serializer.data)

    @extend_schema(
        methods=['patch'],
        summary='Обновить вариант',
        tags=['Merches'],
        description='Обновляет вариант мерча.',
        request=VariantWriteSerializer,
        responses={200: VariantReadSerializer},
    )
    @extend_schema(
        methods=['delete'],
        summary='Удалить вариант',
        tags=['Merches'],
        description='Удаляет вариант мерча.',
        responses={204: None},
    )
    @action(
        detail=True,
        methods=['patch', 'delete'],
        url_path='variants/(?P<variant_id>[0-9]+)',
    )
    def variant_detail(self, request, pk=None, variant_id=None):
        merch = self.get_object()
        variant = get_object_or_404(
            ProductVariant, id=variant_id, product__merch=merch
        )

        if request.method == 'DELETE':
            variant.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = VariantWriteSerializer(
            variant, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(VariantReadSerializer(variant).data)

    @extend_schema(
        summary='Добавить изображение',
        tags=['Merches'],
        description='Добавляет изображение к мерчу.',
        request=ImageSerializer,
        responses={201: ImageSerializer},
    )
    @action(detail=True, methods=['post'], url_path='images')
    def add_image(self, request, pk=None):
        merch = self.get_object()
        serializer = ImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(merch=merch)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        methods=['patch'],
        summary='Обновить изображение',
        tags=['Merches'],
        description='Обновляет изображение мерча.',
        request=ImageSerializer,
        responses={200: ImageSerializer},
    )
    @extend_schema(
        methods=['delete'],
        summary='Удалить изображение',
        tags=['Merches'],
        description='Удаляет изображение мерча.',
        responses={204: None},
    )
    @action(
        detail=True,
        methods=['patch', 'delete'],
        url_path='images/(?P<image_id>[0-9]+)'
    )
    def image_detail(self, request, pk=None, image_id=None):
        merch = self.get_object()
        image = get_object_or_404(Image, id=image_id, merch=merch)

        if request.method == 'DELETE':
            was_main = image.is_main
            image.delete()
            if was_main:
                next_image = merch.images_merch.first()
                if next_image:
                    next_image.is_main = True
                    next_image.save(update_fields=['is_main'])
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = ImageSerializer(image, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
