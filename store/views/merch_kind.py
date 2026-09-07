"""ViewSet для работы с моделью MerchKind."""

from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from store.models import MerchKind
from store.schema import merch_kinds_schema
from store.serializers import MerchKindSerializer


@merch_kinds_schema
class MerchKindViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """API для работы с типами мерча."""

    queryset = MerchKind.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = MerchKindSerializer
    pagination_class = None
