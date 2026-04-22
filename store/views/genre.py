"""ViewSet для работы с моделью Genre."""

from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from store.models import Genre
from store.schema import genre_schema
from store.serializers import GenreSerializer


@genre_schema
class GenreViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """API для работы со справочником жанров."""

    queryset = Genre.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = GenreSerializer
    pagination_class = None
