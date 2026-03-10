"""
ViewSet для управления альбомами.

Предоставляет полный цикл CRUD-операций для модели Album.
"""

from rest_framework import viewsets

from store.models import Album
from store.schema import album_schema
from store.serializers import AlbumReadSerializer, AlbumWriteSerializer


@album_schema
class AlbumViewSet(viewsets.ModelViewSet):
    """API для работы с альбомами."""

    queryset = Album.objects.all()

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return AlbumWriteSerializer
        return AlbumReadSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
