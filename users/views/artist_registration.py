from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny

from .base_registration import BaseRegistrationView
from users.serializers import ArtistRegistrationSerializer


@extend_schema(
    tags=['Регистрация'],
    auth=[],
)
class ArtistRegistrationView(BaseRegistrationView):
    """Представление для регистрации артиста."""

    serializer_class = ArtistRegistrationSerializer
    permission_classes = [AllowAny]
