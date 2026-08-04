from dj_rest_auth.jwt_auth import get_refresh_view
from dj_rest_auth.views import LoginView, LogoutView
from drf_spectacular.utils import extend_schema, extend_schema_view

from users.serializers import (
    CookieLoginResponseSerializer,
    CookieLoginSerializer,
    CookieRefreshResponseSerializer,
)
from users.views.mixins import CookieResponseMixin

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
    ),
)
class CookieLogoutView(LogoutView):
    """Завершает JWT-сессию и удаляет cookie."""


@extend_schema_view(
    post=extend_schema(
        tags=['Auth: JWT cookie'],
        responses={
            200: CookieRefreshResponseSerializer,
        },
    ),
)
class CookieRefreshView(BaseCookieRefreshView):
    """Обновляет JWT-cookie."""
