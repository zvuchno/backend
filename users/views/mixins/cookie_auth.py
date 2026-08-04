from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.response import Response


class CookieResponseMixin:
    """Возвращает единый ответ и устанавливает CSRF-cookie после входа."""

    def get_response(self) -> Response:
        response = super().get_response()
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
