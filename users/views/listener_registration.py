"""Представление для регистрации слушателя."""

from rest_framework.permissions import AllowAny

from .base_registration import BaseRegistrationView
from users.schemas import listener_registration_schema
from users.serializers import ListenerRegistrationSerializer


@listener_registration_schema
class ListenerRegistrationView(BaseRegistrationView):
    """Представление для регистрации слушателя."""

    serializer_class = ListenerRegistrationSerializer
    permission_classes = [AllowAny]
