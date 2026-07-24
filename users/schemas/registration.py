"""Схемы OpenAPI для эндпоинтов регистрации пользователей."""

from drf_spectacular.utils import extend_schema

from users.serializers import ArtistRegistrationSerializer
from users.serializers.artist_registration import (
    ArtistRegistrationResponseSerializer,
)

listener_registration_schema = extend_schema(
    tags=['Registration'],
    auth=[],
    summary='Регистрация слушателя',
    description=(
        'Создает учетную запись пользователя и связанный профиль слушателя.'
    ),
)

artist_registration_schema = extend_schema(
    tags=['Registration'],
    auth=[],
    summary='Регистрация артиста или лейбла',
    description=(
        'Создает учетную запись пользователя, профиль слушателя '
        'и связанный профиль артиста или лейбла. '
        'Тип профиля определяется полем profile_type.'
    ),
    request=ArtistRegistrationSerializer,
    responses={
        201: ArtistRegistrationResponseSerializer,
    },
)
