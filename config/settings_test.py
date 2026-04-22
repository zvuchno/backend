"""Настройки для тестового окружения.

Расширяет базовые настройки Django и переопределяет параметры,
специфичные для тестов.
"""

from .settings import *  # noqa

# Заменяет стандартный хешер паролей на
# MD5PasswordHasher для ускорения выполнения тестов
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]
