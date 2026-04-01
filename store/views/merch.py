from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from store.models import Merch
from store.serializers import (
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

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
