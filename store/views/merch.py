from django.db import transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.permissions import IsArtist, IsStoreObjectOwnerOrReadOnly

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
from store.views.mixins import ProductActionMixin, SoftDeleteMixin


@merch_schema
class MerchViewSet(SoftDeleteMixin, ProductActionMixin, viewsets.ModelViewSet):
    """API для работы с мерчем."""

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

    def get_permissions(self):
        if self.action == 'create':
            return (IsArtist(),)
        return (IsStoreObjectOwnerOrReadOnly(),)

    def get_serializer_class(self):
        if self.action == 'list':
            return MerchReadSerializer
        if self.action == 'retrieve':
            return MerchDetailSerializer
        return MerchWriteSerializer

    def get_queryset(self):
        queryset = Merch.objects.visible_for(self.request.user, self.action)
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
                'owner',
            ).prefetch_related(
                'images_merch',
                'product__variants',
            )
        return queryset

    @add_image_schema
    @action(detail=True, methods=['post'], url_path='images')
    def add_image(self, request, pk=None):
        merch = self.get_object()
        serializer = ImageSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(merch=merch)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @image_detail_schema
    @action(
        detail=True,
        methods=['patch', 'delete'],
        url_path='images/(?P<image_id>[0-9]+)',
    )
    def image_detail(self, request, pk=None, image_id=None):
        merch = self.get_object()
        image = get_object_or_404(Image, id=image_id, merch=merch)

        if request.method == 'DELETE':
            with transaction.atomic():
                was_main = image.is_main
                image_file = image.image
                image.delete()
                transaction.on_commit(lambda: image_file.delete(save=False))
                if was_main:
                    next_image = merch.images_merch.first()
                    if next_image:
                        next_image.is_main = True
                        next_image.save(update_fields=['is_main'])
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = ImageSerializer(
            image,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            was_main = image.is_main
            serializer.save()
            if was_main and not serializer.instance.is_main:
                next_image = merch.images_merch.exclude(id=image.id).first()
                if next_image:
                    next_image.is_main = True
                    next_image.save(update_fields=['is_main'])

        return Response(serializer.data)
