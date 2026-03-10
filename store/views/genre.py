from rest_framework import viewsets

from store.models import Genre
from store.serializers import GenreSerializer


@genre_schema
class GenreViewSet(viewsets.ModelViewSet):
    """API для работы с жанрами."""

    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
