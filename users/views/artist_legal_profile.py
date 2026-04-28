"""Представления для юр профиля артиста."""

from http import HTTPStatus

from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from common.permissions import IsArtist

from users.models import ArtistLegalProfile
from users.schemas import artist_legal_data_schema
from users.serializers import ArtistLegalSerializer


@artist_legal_data_schema
class ArtistLegalProfileView(APIView):
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

    def _get_legal_profile(self) -> ArtistLegalProfile:
        """Возвращает юридический профиль текущего пользователя.

        Если профиль отсутствует, создаёт его.
        """
        legal_profile, _ = (
            ArtistLegalProfile.objects.with_legal_data().get_or_create(
                user=self.request.user,
            )
        )
        return legal_profile

    def get(self, request):
        """Возвращает агрегированные юридические данные артиста."""
        serializer = ArtistLegalSerializer(self._get_legal_profile())
        return Response(serializer.data)

    def patch(self, request):
        """Частично обновляет юридические данные артиста."""
        serializer = ArtistLegalSerializer(
            self._get_legal_profile(),
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=HTTPStatus.OK)
