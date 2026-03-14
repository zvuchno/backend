"""ViewSet для работы с моделью Genre.

Предоставляет полный цикл CRUD-операций для модели Genre.
"""

from rest_framework import viewsets

from store.models import Genre
from store.schema import genre_schema
from store.serializers import GenreSerializer


@genre_schema
class GenreViewSet(viewsets.ModelViewSet):
    """API для работы с жанрами."""

    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
