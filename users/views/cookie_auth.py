from dj_rest_auth.jwt_auth import get_refresh_view
from dj_rest_auth.views import LoginView, LogoutView
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from users.serializers import (
    CookieLoginResponseSerializer,
    CookieLoginSerializer,
    CookieRefreshResponseSerializer,
)
from users.views.mixins import CookieRefreshResponseMixin, CookieResponseMixin

BaseCookieRefreshView = get_refresh_view()


@extend_schema_view(
    post=extend_schema(
        tags=['Auth: JWT cookie'],
        request=CookieLoginSerializer,
        responses={
            200: CookieLoginResponseSerializer,
        },
    ),
)
class CookieLoginView(CookieResponseMixin, LoginView):
    """Создаёт JWT-сессию с токенами в HttpOnly cookie."""


@extend_schema_view(
    post=extend_schema(
        tags=['Auth: JWT cookie'],
        request=None,
        responses={
            200: OpenApiResponse(
                description='JWT-cookie успешно удалены.',
            ),
        },
    ),
)
class CookieLogoutView(LogoutView):
    """Завершает JWT-сессию и удаляет cookie."""

    http_method_names = ['post', 'options']


@extend_schema_view(
    post=extend_schema(
        tags=['Auth: JWT cookie'],
        request=None,
        responses={
            200: CookieRefreshResponseSerializer,
        },
    ),
)
class CookieRefreshView(CookieRefreshResponseMixin, BaseCookieRefreshView):
    """Обновляет JWT-cookie."""
