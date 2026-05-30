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
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@test.local'
