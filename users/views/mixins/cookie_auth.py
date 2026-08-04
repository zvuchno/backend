from rest_framework.response import Response


class CookieResponseMixin:
    """Возвращает единый ответ после создания cookie-сессии."""

    def get_response(self) -> Response:
        response = super().get_response()
        response.data = {
            'authenticated': True,
        }
        return response
