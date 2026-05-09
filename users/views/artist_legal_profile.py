"""Представления для юр профиля артиста."""

from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
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
from users.serializers import (
    ArtistLegalProfileSerializer,
    ArtistLegalSerializer,
)


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

    def get_queryset(self):
        queryset = ArtistLegalProfile.objects.all()

        if self.request.method in SAFE_METHODS:
            return queryset.with_legal_data()

        return queryset

    def get_object(self) -> ArtistLegalProfile | None:
        queryset = self.get_queryset()

        if self.request.method in SAFE_METHODS:
            return queryset.filter(user=self.request.user).first()

        legal_profile, _ = queryset.get_or_create(
            user=self.request.user,
            defaults={
                'email': self.request.user.email,
                'phone': self.request.user.phone,
            },
        )
        return legal_profile

    def get(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance is None:
            legal_profile = ArtistLegalProfile(
                user=request.user,
                email=request.user.email,
                phone=request.user.phone,
            )
            return Response({
                'legal_profile': ArtistLegalProfileSerializer(
                    legal_profile,
                    context=self.get_serializer_context(),
                ).data,
                'identity_data': None,
                'bank_data': None,
                'company_data': None,
            })

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


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
