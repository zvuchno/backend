"""Настройки для тестового окружения.

Расширяет базовые настройки Django и переопределяет параметры,
специфичные для тестов.
"""

import pathlib
import tempfile

from .settings import *  # noqa

# Заменяет стандартный хешер паролей на
# MD5PasswordHasher для ускорения выполнения тестов
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@test.local'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'zvuchno-tests',
    },
}

USE_S3_MEDIA = False

TEST_MEDIA_ROOT = pathlib.Path(tempfile.gettempdir()) / 'zvuchno-test-media'

MEDIA_ROOT = TEST_MEDIA_ROOT
MEDIA_URL = '/media/'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
        'OPTIONS': {
            'location': TEST_MEDIA_ROOT / 'private',
            'base_url': '/media/private/',
        },
    },
    'public_media': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
        'OPTIONS': {
            'location': TEST_MEDIA_ROOT / 'public',
            'base_url': '/media/public/',
        },
    },
    'private_media': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
        'OPTIONS': {
            'location': TEST_MEDIA_ROOT / 'private',
            'base_url': '/media/private/',
        },
    },
    'staticfiles': {
        'BACKEND': ('django.contrib.staticfiles.storage.StaticFilesStorage'),
    },
}
