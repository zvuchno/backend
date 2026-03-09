from rest_framework import viewsets

from ..models import Genre
from ..serializers import GenreSerializer


class GenreViewSet(viewsets.ModelViewSet):
    """API для работы с жанрами."""

    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
