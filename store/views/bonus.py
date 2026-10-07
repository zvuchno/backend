"""ViewSet для работы с моделью бонусов."""

from django.db.models import Q
from rest_framework import viewsets

from common.access import managed_artist_q
from common.permissions import (
    IsArtistOrLabel,
    IsStoreObjectManager,
)

from .mixins import SoftDeleteMixin
from store.filters import BonusFilter
from store.models import Bonus
from store.schema import bonus_schema
from store.serializers import (
    BonusReadDetailSerializer,
    BonusReadSerializer,
    BonusWriteSerializer,
)


@bonus_schema
class BonusViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """API для работы с бонусами."""

    queryset = Bonus.objects.all()
    permission_classes = (IsArtistOrLabel, IsStoreObjectManager)
    http_method_names = ('get', 'post', 'patch', 'delete')
    filterset_class = BonusFilter
    ordering = ('name',)

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return BonusWriteSerializer
        if self.action == 'retrieve':
            return BonusReadDetailSerializer
        return BonusReadSerializer

    def get_queryset(self):
        """Возвращает бонусы, доступные текущему пользователю."""
        user = self.request.user
        queryset = (
            super()
            .get_queryset()
            .select_related(
                'album',
                'album__artist',
            )
        )

        if not user.is_authenticated:
            return queryset.none()

        return queryset.filter(
            Q(is_active=True) & managed_artist_q(user, prefix='album__artist'),
        )
