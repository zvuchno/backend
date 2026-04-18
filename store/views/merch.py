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
