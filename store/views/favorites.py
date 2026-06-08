"""ViewSet для работы с моделью Favorites."""

from rest_framework import mixins, viewsets

from common.permissions import IsUserObjectOwner

from store.models import Favorite
from store.schema import favorites_schema
from store.serializers import FavoriteReadSerializer, FavoriteWriteSerializer


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

    def get_queryset(self):
        return (
            Favorite.objects
            .with_target_annotations()
            .filter(user=self.request.user)
            .select_related('product_variant__product')
        )

    def get_serializer_class(self):
        if self.action in ('create',):
            return FavoriteWriteSerializer
        return FavoriteReadSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
