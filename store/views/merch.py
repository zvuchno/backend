from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from store.models import Image, Merch
from store.serializers import (
    ImageSerializer,
    MerchDetailSerializer,
    MerchReadSerializer,
    MerchWriteSerializer,
)


class MerchViewSet(viewsets.ModelViewSet):
    """API для работы с мерчем."""

    queryset = Merch.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)
    http_method_names = ('get', 'post', 'patch', 'delete')

    def get_serializer_class(self):
        if self.action == 'list':
            return MerchReadSerializer
        if self.action == 'retrieve':
            return MerchDetailSerializer
        return MerchWriteSerializer

    @action(detail=True, methods=['post'], url_path='images')
    def add_image(self, request, pk=None):
        merch = self.get_object()
        serializer = ImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(merch=merch)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=['patch'],
        url_path='images/(?P<image_id>[0-9]+)'
    )
    def update_image(self, request, pk=None, image_id=None):
        merch = self.get_object()
        image = get_object_or_404(Image, id=image_id, merch=merch)
        serializer = ImageSerializer(image, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(
            detail=True,
            methods=['delete'],
            url_path='images/(?P<image_id>[0-9]+)'
        )
    def delete_image(self, request, pk=None, image_id=None):
        merch = self.get_object()
        image = get_object_or_404(Image, id=image_id, merch=merch)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
