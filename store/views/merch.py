from rest_framework import viewsets

from store.models.merch import Merch
from store.serializers.merch import MerchReadSerializer, MerchWriteSerializer


class MerchViewSet(viewsets.ModelViewSet):
    """Вьюсет мерча."""

    queryset = Merch.objects.all()

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return MerchReadSerializer
        return MerchWriteSerializer

    def perform_create(self, serializer):
        return serializer.save(owner=self.request.user)
