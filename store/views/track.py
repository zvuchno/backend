"""
ViewSet для работы с моделью track.

Предоставляет полный цикл CRUD-операций для модели Genre.
"""

from rest_framework import viewsets

from store.models import Track
from store.schema import track_schema
from store.serializers import TrackSerializer


@track_schema
class TrackViewSet(viewsets.ModelViewSet):
    """API для работы с треками."""

    queryset = Track.objects.all()
    serializer_class = TrackSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
