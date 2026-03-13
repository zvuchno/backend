"""
ViewSet для работы с моделью track.

Предоставляет полный цикл CRUD-операций для модели Genre.

TODO:
    - фильтрация
    - поиск
    - permissions
    - пагинация
"""

from rest_framework import viewsets

from store.models import Track
from store.schema import track_schema
from store.serializers import TrackReadSerializer, TrackWriteSerializer


@track_schema
class TrackViewSet(viewsets.ModelViewSet):
    """API для работы с треками."""

    queryset = Track.objects.select_related('album', 'owner').all()

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return TrackWriteSerializer
        return TrackReadSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
