from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.permissions import IsStoreObjectOwnerOrReadOnly

from store.filters.merch import MerchFilter
from store.models import Image, Merch
from store.schema.merch import merch_schema
from store.serializers import (
    ImageSerializer,
    MerchDetailSerializer,
    MerchReadSerializer,
    MerchWriteSerializer,
)
from store.views.mixins import ProductActionMixin


@merch_schema
class MerchViewSet(ProductActionMixin, viewsets.ModelViewSet):
    """API для работы с мерчем."""

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
            .prefetch_related('images_merch')
        )

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated()]
        return [IsStoreObjectOwnerOrReadOnly()]

    @extend_schema(
        summary='Добавить изображение',
        tags=['Merch'],
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
        tags=['Merch'],
        description='Обновляет изображение мерча.',
        request=ImageSerializer,
        responses={200: ImageSerializer},
    )
    @extend_schema(
        methods=['delete'],
        summary='Удалить изображение',
        tags=['Merch'],
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
            image.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = ImageSerializer(image, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
