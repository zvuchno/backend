"""Схемы OpenAPI для API плеера."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status

from store.serializers import (
    PlaybackNotReadySerializer,
    PlayerAlbumSerializer,
)

PLAYER_TAGS = ['Player']


player_album_schema = extend_schema(
    summary='Получить очередь воспроизведения релиза',
    description=(
        'Возвращает альбом и доступные для текущего пользователя треки '
        'в порядке их позиции. '
        'Каждый трек содержит товарные данные и объект playback. '
        'Поле playback.duration показывает длительность фактически '
        'доступного источника, которая может отличаться от полной '
        'длительности трека.'
    ),
    tags=PLAYER_TAGS,
    auth=[],
    responses={
        status.HTTP_200_OK: PlayerAlbumSerializer,
        status.HTTP_404_NOT_FOUND: OpenApiResponse(
            description='Релиз не найден или недоступен.',
        ),
    },
)


player_track_play_schema = extend_schema(
    summary='Запустить воспроизведение трека',
    description=(
        'Проверяет доступность трека и перенаправляет браузер на '
        'подходящий источник аудио. '
        'Сейчас доступно публичное preview; позднее endpoint сможет '
        'выбирать полный stream для пользователя с правом доступа. '
        'Клиенту следует передавать этот URL непосредственно в src '
        'элемента audio и позволить браузеру обработать redirect.'
    ),
    tags=PLAYER_TAGS,
    auth=[],
    responses={
        status.HTTP_302_FOUND: OpenApiResponse(
            description=(
                'Перенаправление на аудиофайл. '
                'Адрес источника передаётся в заголовке Location.'
            ),
        ),
        status.HTTP_404_NOT_FOUND: OpenApiResponse(
            description=(
                'Трек не найден, недоступен или preview временно '
                'не содержит готового файла.'
            ),
        ),
        status.HTTP_409_CONFLICT: PlaybackNotReadySerializer,
    },
)
