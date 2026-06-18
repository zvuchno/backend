import hashlib
import json
import logging
import re
import shutil
import tempfile
import zipfile
from collections.abc import Sequence
from pathlib import Path

from django.core.files import File
from django.utils import timezone

from store.models import Album, AlbumArchive, Track

logger = logging.getLogger(__name__)


class AlbumArchiveService:
    """Собирает ZIP-архив из оригинальных файлов треков альбома."""

    HASH_VERSION = 1
    COPY_BUFFER_SIZE = 1024 * 1024
    MAX_ERROR_MESSAGE_LENGTH = 1000

    @classmethod
    def calculate_content_hash(
        cls,
        *,
        album: Album,
        tracks: Sequence[Track],
    ) -> str:
        """Возвращает отпечаток содержимого будущего архива."""
        payload = {
            'version': cls.HASH_VERSION,
            'album_id': album.id,
            'cover_image': (
                album.cover_image.name if album.cover_image else None
            ),
            'tracks': [
                {
                    'id': track.id,
                    'position': track.position,
                    'name': track.name,
                    'audio_file': (
                        track.audio_file.name if track.audio_file else None
                    ),
                }
                for track in tracks
            ],
        }

        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        )

        return hashlib.sha256(
            serialized.encode('utf-8'),
        ).hexdigest()

    @classmethod
    def build(cls, album_id: int) -> AlbumArchive:
        """Собирает и сохраняет актуальный архив альбома."""
        album = Album.objects.get(pk=album_id)
        tracks = list(
            album.tracks.order_by('position', 'id'),
        )

        if not tracks:
            raise ValueError(
                f'Невозможно собрать архив альбома {album.pk}: '
                'в альбоме нет треков.',
            )

        content_hash = cls.calculate_content_hash(
            album=album,
            tracks=tracks,
        )

        archive = cls._mark_as_building(album)
        old_file_name = archive.file.name or None

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_zip_path = Path(temp_dir) / cls._get_archive_filename(
                    album,
                )

                cls._write_zip(
                    album=album,
                    tracks=tracks,
                    target_path=temp_zip_path,
                )

                with temp_zip_path.open('rb') as zip_to_upload:
                    archive.file.save(
                        cls._get_archive_filename(album),
                        File(zip_to_upload),
                        save=False,
                    )

                archive.status = AlbumArchive.Status.READY
                archive.content_hash = content_hash
                archive.error_message = ''
                archive.save(
                    update_fields=(
                        'file',
                        'status',
                        'content_hash',
                        'error_message',
                        'updated_at',
                    ),
                )

        except Exception as error:
            logger.exception(
                'Ошибка при сборке архива для альбома %s.',
                album_id,
            )
            AlbumArchive.objects.filter(pk=archive.pk).update(
                status=AlbumArchive.Status.FAILED,
                error_message=str(error)[: cls.MAX_ERROR_MESSAGE_LENGTH],
                updated_at=timezone.now(),
            )
            raise

        cls._delete_replaced_file(
            archive=archive,
            old_file_name=old_file_name,
        )

        return archive

    @staticmethod
    def _mark_as_building(album: Album) -> AlbumArchive:
        """Создаёт запись архива и переводит её в статус сборки."""
        archive, _ = AlbumArchive.objects.get_or_create(
            album=album,
        )
        archive.status = AlbumArchive.Status.BUILDING
        archive.error_message = ''
        archive.save(
            update_fields=(
                'status',
                'error_message',
                'updated_at',
            ),
        )
        return archive

    @classmethod
    def _write_zip(
        cls,
        *,
        album: Album,
        tracks: Sequence[Track],
        target_path: Path,
    ) -> None:
        """Создаёт ZIP с обложкой и оригинальными файлами треков."""
        with zipfile.ZipFile(
            target_path,
            mode='w',
            compression=zipfile.ZIP_STORED,
            allowZip64=True,
        ) as zip_file:
            if album.cover_image:
                cls._write_storage_file(
                    zip_file=zip_file,
                    field_file=album.cover_image,
                    entry_name=cls._get_cover_filename(album),
                )

            for track in tracks:
                if not track.audio_file:
                    raise ValueError(
                        f'У трека {track.pk} отсутствует исходный файл.',
                    )

                cls._write_storage_file(
                    zip_file=zip_file,
                    field_file=track.audio_file,
                    entry_name=cls._get_track_filename(track),
                )

    @classmethod
    def _write_storage_file(
        cls,
        *,
        zip_file: zipfile.ZipFile,
        field_file,
        entry_name: str,
    ) -> None:
        """Копирует файл из storage внутрь ZIP небольшими блоками."""
        with field_file.storage.open(
            field_file.name,
            mode='rb',
        ) as source:
            with zip_file.open(
                entry_name,
                mode='w',
                force_zip64=True,
            ) as target:
                shutil.copyfileobj(
                    source,
                    target,
                    length=cls.COPY_BUFFER_SIZE,
                )

    @classmethod
    def _get_track_filename(cls, track: Track) -> str:
        """Возвращает безопасное имя трека внутри архива."""
        suffix = Path(track.audio_file.name).suffix.lower()
        position = str(track.position or 0).zfill(2)
        safe_name = cls._sanitize_filename(track.name)

        return f'{position} - {safe_name}{suffix}'

    @staticmethod
    def _sanitize_filename(value: str) -> str:
        """Удаляет из имени символы, опасные для путей внутри ZIP."""
        value = re.sub(r'[\\/:*?"<>|]+', ' - ', value)
        value = re.sub(r'\s+', ' ', value).strip(' .')

        return value or 'track'

    @staticmethod
    def _get_archive_filename(album: Album) -> str:
        """Возвращает имя ZIP-файла для storage."""
        return f'album-{album.pk}.zip'

    @staticmethod
    def _get_cover_filename(album: Album) -> str:
        """Возвращает имя обложки внутри архива."""
        suffix = Path(album.cover_image.name).suffix.lower()

        return f'cover{suffix}' if suffix else 'cover'

    @staticmethod
    def _delete_replaced_file(
        *,
        archive: AlbumArchive,
        old_file_name: str | None,
    ) -> None:
        """Удаляет прежний архив после успешного сохранения нового."""
        if not old_file_name or old_file_name == archive.file.name:
            return

        try:
            archive.file.storage.delete(old_file_name)
        except Exception:
            logger.exception(
                'Не удалось удалить старый архив %s.',
                old_file_name,
            )
