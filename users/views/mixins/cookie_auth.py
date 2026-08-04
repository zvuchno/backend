from django.middleware.csrf import get_token
from rest_framework.response import Response


class CookieResponseMixin:
    """Возвращает единый ответ после создания cookie-сессии."""

    def get_response(self) -> Response:
        response = super().get_response()
        get_token(self.request)  # CSRF
        response.data = {
            'authenticated': True,
        }
        return response


class CookieRefreshResponseMixin:
    """Возвращает единый ответ после обновления JWT-cookie."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.data = {
            'refreshed': True,
        }
        return response
