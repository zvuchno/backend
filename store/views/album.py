from rest_framework import viewsets

from store.models import Album
from store.serializers import AlbumReadSerializer, AlbumWriteSerializer


class AlbumViewSet(viewsets.ModelViewSet):
    """Управление альбомами."""

    queryset = Album.objects.all()

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return AlbumWriteSerializer
        return AlbumReadSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
