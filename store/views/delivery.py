"""ViewSet для работы с моделью Delivery."""

from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from store.models import Delivery
from store.schema import delivery_schema
from store.serializers import DeliverySerializer


@delivery_schema
class DeliveryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """API для получения вариантов доставки."""

    queryset = Delivery.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = DeliverySerializer
    pagination_class = None
