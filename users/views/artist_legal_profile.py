"""Представления для юр профиля артиста."""

from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from common.permissions import IsArtist
from common.serializers import ChoiceSerializer

from users.models import ArtistLegalProfile
from users.schemas import (
    artist_legal_data_schema,
    recipient_type_list_schema,
)
from users.serializers import ArtistLegalSerializer


@artist_legal_data_schema
class ArtistLegalProfileView(RetrieveUpdateAPIView):
    """API для работы с юридическими данными текущего артиста.

    Позволяет получить и частично обновить данные, связанные с выплатами:
    - юридический профиль: организационная форма получателя;
    - паспортные данные и ИНН физлица / ИП / СМЗ;
    - данные юридического лица;
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


@recipient_type_list_schema
class RecipientTypeListView(APIView):
    """Справочник организационных форм получателя выплат."""

    permission_classes = [IsAuthenticated]
    serializer_class = ChoiceSerializer

    def get(self, request):
        """Возвращает доступные формы организаций."""
        data = [
            {'value': value, 'label': label}
            for value, label in ArtistLegalProfile.RecipientType.choices
        ]
        return Response(ChoiceSerializer(data, many=True).data)
