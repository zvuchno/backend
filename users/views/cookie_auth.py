from dj_rest_auth.jwt_auth import get_refresh_view
from dj_rest_auth.views import LoginView, LogoutView
from drf_spectacular.utils import extend_schema

from users.serializers import (
    SessionLoginResponseSerializer,
    SessionLoginSerializer,
)
from users.views.mixins import SessionResponseMixin

BaseCookieRefreshView = get_refresh_view()


@extend_schema(
    tags=['Auth: JWT Cookie'],
    request=SessionLoginSerializer,
    responses={
        200: SessionLoginResponseSerializer,
    },
)
class CookieLoginView(SessionResponseMixin, LoginView):
    """Создаёт JWT-сессию с токенами в HttpOnly cookie."""


@extend_schema(
    tags=['Auth: JWT Cookie'],
)
class CookieLogoutView(LogoutView):
    """Завершает JWT-сессию и удаляет cookie."""


@extend_schema(
    tags=['Auth: JWT Cookie'],
)
class CookieRefreshView(BaseCookieRefreshView):
    """Обновляет JWT-cookie."""
