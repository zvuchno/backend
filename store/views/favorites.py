"""ViewSet для работы с моделью Favorites."""

from rest_framework import mixins, viewsets

from common.permissions import IsUserObjectOwner

from store.models import Favorite
from store.schema import favorites_schema
from store.serializers import FavoritesSerializer


@favorites_schema
class FavoritesViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """API модели избранного."""

    queryset = Favorite.objects.all()
    permission_classes = (IsUserObjectOwner,)
    serializer_class = FavoritesSerializer

    def get_queryset(self):
        return Favorite.objects.filter(
            user=self.request.user,
        ).select_related('product_variant__product')
