"""Представления профиля артиста."""

from django.db.models import Case, Q, When
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.generics import (
    GenericAPIView,
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
    UpdateAPIView,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from common.permissions import IsLabel, IsNotArtist

from users.filters import ArtistFilter
from users.models import ArtistProfile
from users.schemas import (
    artist_cover_update_schema,
    artist_list_schema,
    artist_me_schema,
    artist_public_schema,
    become_artist_schema,
)
from users.serializers.artist_profile import (
    ArtistCoverUpdateSerializer,
    ArtistMeSerializer,
    ArtistMeUpdateSerializer,
    ArtistPublicSerializer,
    ArtistPublicShortSerializer,
    BecomeArtistOrLabelSerializer,
    ManagedArtistProfileSerializer,
)
from users.views.mixins import CurrentArtistProfileMixin


@artist_cover_update_schema
class ArtistCoverUpdateView(CurrentArtistProfileMixin, UpdateAPIView):
    """Обновление обложки артиста."""

    permission_classes = [IsAuthenticated]
    serializer_class = ArtistCoverUpdateSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ['patch']

    def get_object(self):
        """Возвращает профиль артиста текущего пользователя."""
        return self.get_artist_profile()


@artist_me_schema
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


@artist_public_schema
class ArtistPublicView(RetrieveAPIView):
    """Публичный просмотр профиля артиста."""

    queryset = ArtistProfile.objects.filter(is_active=True).prefetch_related(
        'contacts',
        'socials',
    )
    permission_classes = [AllowAny]
    serializer_class = ArtistPublicSerializer
    lookup_field = 'slug'


@artist_list_schema
class ArtistListView(ListAPIView):
    """Публичный список артистов."""

    queryset = ArtistProfile.objects.filter(
        is_active=True,
    ).select_related('user')
    permission_classes = [AllowAny]
    serializer_class = ArtistPublicShortSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_class = ArtistFilter
    search_fields = ['name', 'slug', 'city']
    ordering_fields = ['name', 'created_at']
    ordering = ['name', '-created_at']


@become_artist_schema
class BecomeArtistOrLabelView(GenericAPIView):
    """Представление для создания профиля артиста или лейбла."""

    serializer_class = BecomeArtistOrLabelSerializer
    permission_classes = [IsAuthenticated, IsNotArtist]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'become_artist'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        artist = serializer.save()
        response_serializer = self.get_serializer(artist)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class LabelManagedArtistListView(ListAPIView):
    """Список артистов текущего лейбла."""

    permission_classes = [IsLabel]
    serializer_class = ManagedArtistProfileSerializer

    def get_queryset(self):
        """Возвращает профили, доступные текущему лейблу для управления."""
        label = self.request.user.artist_profile

        return (
            ArtistProfile.objects
            .filter(
                Q(pk=label.pk) | Q(label=label),
                is_active=True,
            )
            .select_related('user')
            .order_by(
                Case(
                    When(pk=label.pk, then=0),
                    default=1,
                ),
                'name',
            )
        )
