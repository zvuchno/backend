"""Представления для юр профиля артиста."""

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

    def get(self, request):
        legal_profile, _ = ArtistLegalProfile.objects.get_or_create(
            user=request.user,
        )
        serializer = ArtistLegalSerializer(legal_profile)
        return Response(serializer.data)

    def patch(self, request):
        legal_profile, _ = ArtistLegalProfile.objects.get_or_create(
            user=request.user,
        )
        serializer = ArtistLegalSerializer(
            legal_profile,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
