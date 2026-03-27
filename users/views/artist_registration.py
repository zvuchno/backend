from rest_framework.permissions import AllowAny

from .base_registration import BaseRegistrationView
from users.schemas import artist_registration_schema
from users.serializers import ArtistRegistrationSerializer


@artist_registration_schema
class ArtistRegistrationView(BaseRegistrationView):
    """Представление для регистрации артиста."""

    serializer_class = ArtistRegistrationSerializer
    permission_classes = [AllowAny]
