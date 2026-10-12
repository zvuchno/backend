from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.response import Response

from users.helpers import run_actions_after_authentication


class CookieResponseMixin:
    """Возвращает единый ответ и устанавливает CSRF-cookie после входа."""

    def get_response(self) -> Response:
        response = super().get_response()

        auth_actions_kwargs = {}
        if hasattr(self, 'pre_auth_session_key'):
            auth_actions_kwargs['session_key'] = self.pre_auth_session_key

        run_actions_after_authentication(
            self.user,
            self.request,
            **auth_actions_kwargs,
        )

        get_token(self.request)
        response.data = {
            'authenticated': True,
        }
        return response


class CookieRefreshResponseMixin:
    """Возвращает единый ответ после обновления JWT-cookie."""

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(
            request,
            response,
            *args,
            **kwargs,
        )

        if response.status_code == status.HTTP_200_OK:
            response.data = {
                'refreshed': True,
            }

        return response
