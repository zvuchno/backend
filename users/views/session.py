from dj_rest_auth.views import LoginView
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from users.serializers import (
    SessionLoginResponseSerializer,
    SessionLoginSerializer,
)


@extend_schema(
    request=SessionLoginSerializer,
    responses={
        200: SessionLoginResponseSerializer,
    },
)
class SessionLoginView(LoginView):
    """Выполняет вход и устанавливает JWT в HttpOnly cookie."""

    def get_response(self) -> Response:
        response = super().get_response()
        response.data = {
            'authenticated': True,
        }
        return response
