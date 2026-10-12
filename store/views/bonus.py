"""ViewSet для работы с моделью бонусов."""

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.access import managed_artist_q
from common.permissions import (
    IsArtistOrLabel,
    IsStoreObjectManager,
)

from .mixins import SoftDeleteMixin
from store.filters import BonusFilter
from store.models import Bonus
from store.schema import bonus_reorder_schema, bonus_schema
from store.serializers import (
    BonusReadDetailSerializer,
    BonusReadSerializer,
    BonusReorderSerializer,
    BonusWriteSerializer,
)
from store.services import reorder_bonuses


@bonus_schema
class BonusViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """API для работы с бонусами."""

    queryset = Bonus.objects.all()
    permission_classes = (IsArtistOrLabel, IsStoreObjectManager)
    http_method_names = ('get', 'post', 'patch', 'delete')
    filter_backends = (DjangoFilterBackend,)
    filterset_class = BonusFilter

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
            )
        )

        if not user.is_authenticated:
            return queryset.none()

        return queryset.filter(
            Q(is_active=True) & managed_artist_q(user, prefix='album__artist'),
        )

    @bonus_reorder_schema
    @action(
        detail=False,
        methods=['patch'],
        url_path='reorder',
        pagination_class=None,
    )
    def reorder(self, request):
        """Задаёт порядок бонусов альбома за один запрос."""
        serializer = BonusReorderSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        album = serializer.validated_data['album']
        reorder_bonuses(
            album,
            serializer.validated_data['bonus_ids'],
        )

        bonuses = (
            self
            .get_queryset()
            .filter(
                album=album,
            )
            .order_by('position')
        )

        return Response(
            BonusReadSerializer(
                bonuses,
                many=True,
                context=self.get_serializer_context(),
            ).data,
        )
