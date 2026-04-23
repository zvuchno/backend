"""Кастомные исключения."""


class SocialAuthException(Exception):
    """Ошибка аутентификации через сторонний сервис."""

    def __init__(self, error_code: str, message: str):
        """Инициализация исключения."""
        self.error_code = error_code
        self.message = message
        super().__init__(message)
