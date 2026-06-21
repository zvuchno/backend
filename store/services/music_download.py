"""Формирование временных ссылок на приватные медиафайлы."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class DownloadFilenameService:
    """Формирует имена файлов для сохранения пользователем."""

    @classmethod
    def get_track_filename(cls, track) -> str:
        """Возвращает имя отдельного скачиваемого трека."""
        album = track.album
        artist = getattr(album.owner, 'artist_profile', None)

        artist_name = artist.name if artist else 'Исполнитель'
        suffix = Path(track.audio_file.name).suffix.lower()

        album_part = cls._get_album_part(album)
        position_part = (
            f'{track.position:02d} — ' if track.position is not None else ''
        )

        return (
            f'{cls._sanitize(artist_name)} — '
            f'{album_part} — '
            f'{position_part}'
            f'{cls._sanitize(track.name)}{suffix}'
        )

    @classmethod
    def get_archive_filename(cls, album) -> str:
        """Возвращает имя ZIP-архива полного релиза."""
        artist = getattr(album.owner, 'artist_profile', None)
        artist_name = artist.name if artist else 'Исполнитель'

        return (
            f'{cls._sanitize(artist_name)} — {cls._get_album_part(album)}.zip'
        )

    @classmethod
    def _get_album_part(cls, album) -> str:
        """Возвращает нормализованное имя альбома с годом."""
        album_name = cls._sanitize(album.name)

        if album.release_date:
            return f'{album_name} ({album.release_date.year})'

        return album_name

    @staticmethod
    def _sanitize(value: str) -> str:
        """Удаляет опасные символы из имени файла."""
        value = re.sub(r'[\\/:*?"<>|]+', ' - ', value)
        value = re.sub(r'\s+', ' ', value).strip(' .')

        return value or 'download'


@dataclass(frozen=True)
class DownloadLink:
    """Временная ссылка на скачивание файла."""

    url: str
    filename: str
    expires_in: int | None
    expires_at: datetime | None


class DownloadLinkService:
    """Создаёт ссылки на скачивание файлов из настроенного storage."""

    @classmethod
    def get_link(
        cls,
        *,
        field_file,
        filename: str,
    ) -> DownloadLink:
        """Возвращает ссылку на файл и метаданные срока её действия."""
        cls._validate_file(field_file)

        if settings.USE_S3_MEDIA:
            return cls._get_s3_link(
                field_file=field_file,
                filename=filename,
            )

        return cls._get_local_link(
            field_file=field_file,
            filename=filename,
        )

    @staticmethod
    def _validate_file(field_file) -> None:
        """Проверяет наличие файла в модели и storage."""
        if not field_file or not field_file.name:
            logger.warning(
                'Download requested for an empty file field.',
            )
            raise FileNotFoundError('Файл для скачивания отсутствует.')

        if not field_file.storage.exists(field_file.name):
            logger.error(
                'Download requested for a missing storage object: %s',
                field_file.name,
            )
            raise FileNotFoundError('Файл для скачивания не найден.')

    @classmethod
    def _get_s3_link(
        cls,
        *,
        field_file,
        filename: str,
    ) -> DownloadLink:
        """Создаёт временную S3-ссылку с именем файла для браузера."""
        expires_in = settings.AWS_QUERYSTRING_EXPIRE
        expires_at = timezone.now() + timedelta(
            seconds=expires_in,
        )

        url = field_file.storage.url(
            field_file.name,
            parameters={
                'ResponseContentDisposition': (
                    cls._build_content_disposition(filename)
                ),
            },
            expire=expires_in,
        )

        return DownloadLink(
            url=url,
            filename=filename,
            expires_in=expires_in,
            expires_at=expires_at,
        )

    @staticmethod
    def _get_local_link(
        *,
        field_file,
        filename: str,
    ) -> DownloadLink:
        """Возвращает URL локального файла для разработки."""
        return DownloadLink(
            url=field_file.url,
            filename=filename,
            expires_in=None,
            expires_at=None,
        )

    @staticmethod
    def _build_content_disposition(filename: str) -> str:
        """Возвращает UTF-8 Content-Disposition для скачивания файла."""
        encoded_filename = quote(filename, safe='')

        return f"attachment; filename*=UTF-8''{encoded_filename}"
