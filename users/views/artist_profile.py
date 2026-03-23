"""Представления профиля артиста."""

from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework.generics import (
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
    UpdateAPIView,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated

from users.models import ArtistProfile
from users.serializers.artist_profile import (
    ArtistCoverUpdateSerializer,
    ArtistMeSerializer,
    ArtistMeUpdateSerializer,
    ArtistPublicSerializer,
    ArtistPublicShortSerializer,
)


@extend_schema(tags=['Профиль артиста'])
class ArtistCoverUpdateView(UpdateAPIView):
    """Обновление обложки артиста."""

    permission_classes = [IsAuthenticated]
    serializer_class = ArtistCoverUpdateSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ['patch']

    def get_object(self):
        """Возвращает профиль артиста текущего пользователя."""
        try:
            return self.request.user.artist_profile
        except ArtistProfile.DoesNotExist:
            raise Http404('Профиль артиста не найден.')


@extend_schema(tags=['Профиль артиста'])
class ArtistMeView(RetrieveUpdateAPIView):
    """Просмотр и редактирование профиля текущего артиста."""

    # TODO добавить пермишн на владельца
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """Возвращает профиль артиста текущего пользователя."""
        try:
            return self.request.user.artist_profile
        except ArtistProfile.DoesNotExist:
            raise Http404('Профиль артиста не найден.')

    def get_serializer_class(self):
        """Возвращает сериализатор в зависимости от метода запроса."""
        if self.request.method in ('PUT', 'PATCH'):
            return ArtistMeUpdateSerializer
        return ArtistMeSerializer


@extend_schema(tags=['Профиль артиста'], auth=[])
class ArtistPublicView(RetrieveAPIView):
    """Публичный просмотр профиля артиста."""

    queryset = ArtistProfile.objects.filter(is_active=True).prefetch_related(
        'contacts',
        'socials',
    )
    permission_classes = [AllowAny]
    serializer_class = ArtistPublicSerializer
    lookup_field = 'slug'


@extend_schema(tags=['Профиль артиста'], auth=[])
class ArtistListView(ListAPIView):
    """Публичный список артистов."""

    queryset = ArtistProfile.objects.filter(is_active=True)
    permission_classes = [AllowAny]
    serializer_class = ArtistPublicShortSerializer
