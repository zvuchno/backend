"""Представления профиля артиста."""

from django.db.models import Case, Q, When
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.generics import (
    GenericAPIView,
    ListAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
    UpdateAPIView,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from common.permissions import (
    IsArtist,
    IsArtistOrLabel,
    IsLabel,
    IsNotLabel,
)
from common.services import artist_publication_ready_q

from users.filters import ArtistFilter
from users.models import ArtistProfile
from users.schemas import (
    artist_cover_update_schema,
    artist_leave_label_schema,
    artist_list_schema,
    artist_me_schema,
    artist_public_schema,
    become_artist_schema,
    label_managed_profile_list_schema,
    managed_artist_cover_update_schema,
    managed_artist_schema,
)
from users.serializers.artist_profile import (
    ArtistCoverUpdateSerializer,
    ArtistMeSerializer,
    ArtistProfileUpdateSerializer,
    ArtistPublicSerializer,
    ArtistPublicShortSerializer,
    BecomeArtistOrLabelSerializer,
    ManagedArtistProfileCreateSerializer,
    ManagedArtistProfileSerializer,
)
from users.services import ArtistMembershipService
from users.views.mixins import (
    ManagedArtistProfileMixin,
)


class ArtistCoverUpdateBaseView(
    ManagedArtistProfileMixin,
    UpdateAPIView,
):
    """Базовое обновление обложки доступного профиля."""

    permission_classes = [IsArtistOrLabel]
    serializer_class = ArtistCoverUpdateSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ['patch']

    def get_object(self):
        """Возвращает доступный профиль артиста или лейбла."""
        return self.get_artist_profile()


@artist_cover_update_schema
class ArtistCoverUpdateView(ArtistCoverUpdateBaseView):
    """Обновление обложки собственного профиля."""


@managed_artist_cover_update_schema
class ManagedArtistCoverUpdateView(ArtistCoverUpdateBaseView):
    """Обновление обложки управляемого профиля."""


class ArtistProfileBaseView(ManagedArtistProfileMixin, RetrieveUpdateAPIView):
    """Просмотр и редактирование доступного профиля."""

    permission_classes = [IsArtistOrLabel]
    http_method_names = ['get', 'patch']
    select_related = ('label',)
    prefetch_related = ('contacts', 'socials')

    def get_object(self):
        """Возвращает профиль артиста или лейбла."""
        return self.get_artist_profile()

    def get_serializer_class(self):
        """Возвращает сериализатор в зависимости от метода запроса."""
        if self.request.method == 'PATCH':
            return ArtistProfileUpdateSerializer
        return ArtistMeSerializer


@artist_me_schema
class ArtistMeView(ArtistProfileBaseView):
    """Просмотр и редактирование собственного профиля."""


@managed_artist_schema
class ManagedArtistProfileView(ArtistProfileBaseView):
    """Просмотр и редактирование управляемого профиля."""


@artist_public_schema
class ArtistPublicView(RetrieveAPIView):
    """Публичный просмотр профиля артиста."""

    queryset = (
        ArtistProfile.objects
        .filter(is_active=True)
        .select_related('label')
        .prefetch_related(
            'contacts',
            'socials',
        )
    )
    permission_classes = [AllowAny]
    serializer_class = ArtistPublicSerializer
    lookup_field = 'slug'


@artist_list_schema
class ArtistListView(ListAPIView):
    """Публичный список артистов."""

    queryset = ArtistProfile.objects.all()
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

    def get_queryset(self):
        """Возвращает артистов, доступных в публичном списке."""
        return (
            super()
            .get_queryset()
            .filter(
                artist_publication_ready_q(),
                is_active=True,
            )
            .select_related(
                'user',
                'label',
                'label__user',
            )
        )


@become_artist_schema
class BecomeArtistOrLabelView(GenericAPIView):
    """Представление для создания профиля артиста или лейбла."""

    serializer_class = BecomeArtistOrLabelSerializer
    permission_classes = [IsAuthenticated, IsNotLabel]
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


@label_managed_profile_list_schema
class LabelManagedProfileListView(ListCreateAPIView):
    """Список и создание профилей, управляемых текущим лейблом."""

    permission_classes = [IsLabel]
    pagination_class = None

    def get_serializer_class(self):
        """Возвращает сериализатор для требуемой операции."""
        if self.request.method == 'POST':
            return ManagedArtistProfileCreateSerializer
        return ManagedArtistProfileSerializer

    def get_queryset(self):
        """Возвращает профили, доступные текущему лейблу для управления."""
        label = self.request.user.artist_profile

        return (
            ArtistProfile.objects
            .filter(
                Q(pk=label.pk) | Q(label=label),
                is_active=True,
            )
            .select_related(
                'user',
                'label',
                'claim_invitation__invitation',
            )
            .order_by(
                Case(
                    When(pk=label.pk, then=0),
                    default=1,
                ),
                'name',
            )
        )


@artist_leave_label_schema
class ArtistLeaveLabelView(APIView):
    """Самостоятельный выход текущего артиста из лейбла."""

    permission_classes = [IsArtist]

    def post(self, request):
        ArtistMembershipService.leave_label(
            artist=request.user.artist_profile,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
