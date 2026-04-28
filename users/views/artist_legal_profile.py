"""Представления для юр профиля артиста."""

from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.throttling import ScopedRateThrottle

from common.permissions import IsArtist

from users.models import ArtistLegalProfile
from users.schemas import artist_legal_data_schema
from users.serializers import ArtistLegalSerializer


@artist_legal_data_schema
class ArtistLegalProfileView(RetrieveUpdateAPIView):
    """API для работы с юридическими данными текущего артиста.

    Позволяет получить и частично обновить данные, связанные с выплатами:
    - юридический профиль (тип получателя, система налогообложения);
    - паспортные данные;
    - банковские реквизиты.

    Используется для формы "Реквизиты артиста" на фронтенде.
    """

    permission_classes = [IsArtist]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'artist_legal_profile'
    http_method_names = ['get', 'patch']
    serializer_class = ArtistLegalSerializer

    def get_object(self) -> ArtistLegalProfile:
        """Возвращает юридический профиль текущего пользователя.

        Если профиль отсутствует, создаёт его.
        """
        legal_profile, _ = (
            ArtistLegalProfile.objects.with_legal_data().get_or_create(
                user=self.request.user,
            )
        )
        return legal_profile
