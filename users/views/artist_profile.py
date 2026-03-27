"""Представления профиля артиста."""

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
from users.views.mixins import CurrentArtistProfileMixin


@extend_schema(tags=['Profile: artist'])
class ArtistCoverUpdateView(CurrentArtistProfileMixin, UpdateAPIView):
    """Обновление обложки артиста."""

    permission_classes = [IsAuthenticated]
    serializer_class = ArtistCoverUpdateSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ['patch']

    def get_object(self):
        """Возвращает профиль артиста текущего пользователя."""
        return self.get_artist_profile()


@extend_schema(tags=['Profile: artist'])
class ArtistMeView(CurrentArtistProfileMixin, RetrieveUpdateAPIView):
    """Просмотр и редактирование профиля текущего артиста."""

    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'patch']
    select_related = ('user',)
    prefetch_related = ('contacts', 'socials')

    def get_object(self):
        """Возвращает профиль артиста текущего пользователя."""
        return self.get_artist_profile()

    def get_serializer_class(self):
        """Возвращает сериализатор в зависимости от метода запроса."""
        if self.request.method == 'PATCH':
            return ArtistMeUpdateSerializer
        return ArtistMeSerializer


@extend_schema(tags=['Profile: artist'], auth=[])
class ArtistPublicView(RetrieveAPIView):
    """Публичный просмотр профиля артиста."""

    queryset = ArtistProfile.objects.filter(is_active=True).prefetch_related(
        'contacts',
        'socials',
    )
    permission_classes = [AllowAny]
    serializer_class = ArtistPublicSerializer
    lookup_field = 'slug'


# TODO пагинация, фильтрация.
@extend_schema(tags=['Profile: artist'], auth=[])
class ArtistListView(ListAPIView):
    """Публичный список артистов."""

    queryset = ArtistProfile.objects.filter(is_active=True)
    permission_classes = [AllowAny]
    serializer_class = ArtistPublicShortSerializer
