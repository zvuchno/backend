"""Подготовка производных аудиофайлов трека."""

import hashlib
import logging
import socket
import tempfile
from pathlib import Path
from urllib.error import URLError

from django.core.files import File
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from store.exceptions import TemporaryAudioStorageError
from store.models import Recording, TrackGeneratedAudio
from store.services.audio.file_hash import iter_file_chunks
from store.services.audio.processing import AudioProcessingService

logger = logging.getLogger(__name__)


class TrackAudioPreparationService:
    """Подготавливает preview и stream для трека."""

    @classmethod
    def prepare(cls, recording_id: int) -> None:
        """Создаёт производные аудиофайлы для указанной записи."""
        started = cls._start_processing(recording_id=recording_id)
        if started is None:
            return

        recording, generated, source_version = started
        uploaded_files: dict[str, tuple[object, str]] = {}
        component_errors: dict[str, Exception] = {}

        try:
            duration, file_hash, preview_duration = cls._prepare_locally(
                recording=recording,
                generated=generated,
                uploaded_files=uploaded_files,
                component_errors=component_errors,
            )
        except TemporaryAudioStorageError:
            cls._delete_unpublished_files(uploaded_files)
            if cls._source_is_current(
                recording_id=recording.pk,
                source_version=source_version,
            ):
                raise
            return
        except Exception as error:
            cls._delete_unpublished_files(uploaded_files)
            if cls._mark_processing_failed_if_current(
                recording_id=recording.pk,
                source_version=source_version,
                error=error,
            ):
                raise
            return

        try:
            published = cls._publish_results_if_current(
                recording_id=recording.pk,
                source_version=source_version,
                duration=duration,
                file_hash=file_hash,
                preview_duration=preview_duration,
                uploaded_files=uploaded_files,
                component_errors=component_errors,
            )
        except Exception:
            cls._delete_unpublished_files(uploaded_files)
            raise

        if not published:
            cls._delete_unpublished_files(uploaded_files)
            return

        if component_errors:
            raise next(iter(component_errors.values()))

    @classmethod
    def _prepare_locally(
        cls,
        *,
        recording: Recording,
        generated: TrackGeneratedAudio,
        uploaded_files: dict[str, tuple[object, str]],
        component_errors: dict[str, Exception],
    ) -> tuple[int, str, int | None]:
        """Готовит и загружает результаты, не публикуя их в БД."""
        with tempfile.TemporaryDirectory(
            prefix=f'recording-{recording.pk}-',
        ) as temporary_directory:
            workdir = Path(temporary_directory)
            source_path, file_hash = cls._download_source_file(
                recording=recording,
                workdir=workdir,
            )
            metadata = AudioProcessingService.probe_metadata(source_path)
            preview_duration = None

            try:
                stream_path = workdir / 'stream.mp3'
                AudioProcessingService.create_stream(
                    source_path=source_path,
                    target_path=stream_path,
                )
                uploaded_files['stream'] = cls._upload_generated_file(
                    generated=generated,
                    field_name='stream_file',
                    target_path=stream_path,
                    target_filename='stream.mp3',
                )
            except TemporaryAudioStorageError:
                raise
            except Exception as error:
                component_errors['stream'] = error

            try:
                preview_path = workdir / 'preview.mp3'
                preview_duration = AudioProcessingService.create_preview(
                    source_path=source_path,
                    target_path=preview_path,
                    source_duration=metadata.duration,
                )
                uploaded_files['preview'] = cls._upload_generated_file(
                    generated=generated,
                    field_name='preview_file',
                    target_path=preview_path,
                    target_filename='preview.mp3',
                )
            except TemporaryAudioStorageError:
                raise
            except Exception as error:
                component_errors['preview'] = error

        return metadata.duration, file_hash, preview_duration

    @classmethod
    def _start_processing(
        cls,
        *,
        recording_id: int,
    ) -> tuple[Recording, TrackGeneratedAudio, str] | None:
        """Фиксирует версию original и старт короткой транзакцией."""
        with transaction.atomic():
            try:
                recording = Recording.objects.select_for_update().get(
                    pk=recording_id,
                )
            except Recording.DoesNotExist:
                return None

            source_version = recording.audio_file.name
            generated, _ = TrackGeneratedAudio.objects.get_or_create(
                track=recording,
            )
            generated = TrackGeneratedAudio.objects.select_for_update().get(
                pk=generated.pk,
            )
            cls._mark_processing_started(generated)

        return recording, generated, source_version

    @classmethod
    def _upload_generated_file(
        cls,
        *,
        generated: TrackGeneratedAudio,
        field_name: str,
        target_path: Path,
        target_filename: str,
    ) -> tuple[object, str]:
        """Загружает generated-файл под уникальным именем без публикации."""
        field = getattr(generated, field_name)
        storage = field.storage
        storage_name = field.field.generate_filename(
            generated,
            target_filename,
        )

        try:
            with target_path.open('rb') as target_file:
                saved_name = storage.save(
                    storage_name,
                    File(target_file),
                )
        except Exception as error:
            cls._raise_storage_error(error)

        return storage, saved_name

    @classmethod
    def _publish_results_if_current(
        cls,
        *,
        recording_id: int,
        source_version: str,
        duration: int,
        file_hash: str,
        preview_duration: int | None,
        uploaded_files: dict[str, tuple[object, str]],
        component_errors: dict[str, Exception],
    ) -> bool:
        """Атомарно публикует результаты только для текущего original."""
        with transaction.atomic():
            recording = Recording.objects.select_for_update().get(
                pk=recording_id,
            )
            if recording.audio_file.name != source_version:
                return False

            generated = TrackGeneratedAudio.objects.select_for_update().get(
                track_id=recording_id,
            )
            old_files: list[tuple[object, str]] = []

            recording.duration = duration
            recording.file_hash = file_hash
            recording.save(
                update_fields=(
                    'duration',
                    'file_hash',
                    'updated_at',
                ),
            )

            cls._apply_component_result(
                generated=generated,
                component='stream',
                uploaded_files=uploaded_files,
                component_errors=component_errors,
                old_files=old_files,
            )
            cls._apply_component_result(
                generated=generated,
                component='preview',
                uploaded_files=uploaded_files,
                component_errors=component_errors,
                old_files=old_files,
                preview_duration=preview_duration,
            )
            generated.save(
                update_fields=(
                    'preview_file',
                    'preview_duration',
                    'preview_status',
                    'preview_error',
                    'stream_file',
                    'stream_status',
                    'stream_error',
                ),
            )

            for storage, old_name in old_files:
                transaction.on_commit(
                    lambda storage=storage, file_name=old_name: (
                        cls._delete_generated_file_if_unreferenced(
                            storage=storage,
                            file_name=file_name,
                        )
                    ),
                    robust=True,
                )

        return True

    @staticmethod
    def _apply_component_result(
        *,
        generated: TrackGeneratedAudio,
        component: str,
        uploaded_files: dict[str, tuple[object, str]],
        component_errors: dict[str, Exception],
        old_files: list[tuple[object, str]],
        preview_duration: int | None = None,
    ) -> None:
        """Применяет успешный или ошибочный результат одного компонента."""
        file_field = getattr(generated, f'{component}_file')

        if component in uploaded_files:
            storage, new_name = uploaded_files[component]
            old_name = file_field.name
            file_field.name = new_name
            setattr(
                generated,
                f'{component}_status',
                TrackGeneratedAudio.ProcessingStatus.READY,
            )
            setattr(generated, f'{component}_error', '')

            if component == 'preview':
                generated.preview_duration = preview_duration

            if old_name and old_name != new_name:
                old_files.append((storage, old_name))
            return

        error = component_errors[component]
        setattr(
            generated,
            f'{component}_status',
            TrackGeneratedAudio.ProcessingStatus.FAILED,
        )
        setattr(generated, f'{component}_error', str(error)[:2000])

    @classmethod
    def _mark_processing_failed_if_current(
        cls,
        *,
        recording_id: int,
        source_version: str,
        error: Exception,
    ) -> bool:
        """Записывает общую ошибку, только пока original не заменён."""
        with transaction.atomic():
            recording = Recording.objects.select_for_update().get(
                pk=recording_id,
            )
            if recording.audio_file.name != source_version:
                return False

            generated = TrackGeneratedAudio.objects.select_for_update().get(
                track_id=recording_id,
            )
            cls._mark_processing_failed(
                generated=generated,
                error=error,
            )

        return True

    @staticmethod
    def _source_is_current(*, recording_id: int, source_version: str) -> bool:
        """Проверяет актуальность версии original без изменения состояния."""
        return Recording.objects.filter(
            pk=recording_id,
            audio_file=source_version,
        ).exists()

    @classmethod
    def _delete_unpublished_files(
        cls,
        uploaded_files: dict[str, tuple[object, str]],
    ) -> None:
        """Удаляет загруженные, но не опубликованные generated-файлы."""
        for storage, file_name in uploaded_files.values():
            cls._delete_storage_file(storage, file_name)

    @classmethod
    def _delete_generated_file_if_unreferenced(
        cls,
        *,
        storage,
        file_name: str,
    ) -> None:
        """Удаляет прежний файл, если он больше не опубликован."""
        is_referenced = TrackGeneratedAudio.objects.filter(
            Q(preview_file=file_name) | Q(stream_file=file_name),
        ).exists()
        if not is_referenced:
            cls._delete_storage_file(storage, file_name)

    @classmethod
    def _download_source_file(
        cls,
        *,
        recording: Recording,
        workdir: Path,
    ) -> tuple[Path, str]:
        """Скачивает оригинал и вычисляет его SHA-256."""
        suffix = Path(recording.audio_file.name).suffix.lower()
        source_path = workdir / f'original{suffix}'
        hasher = hashlib.sha256()

        try:
            with recording.audio_file.open('rb') as source_file:
                with source_path.open('wb') as target_file:
                    for chunk in iter_file_chunks(source_file):
                        hasher.update(chunk)
                        target_file.write(chunk)
        except Exception as error:
            cls._raise_storage_error(error)

        return source_path, hasher.hexdigest()

    @staticmethod
    def _mark_processing_started(
        generated: TrackGeneratedAudio,
    ) -> None:
        """Переводит производные файлы в статус подготовки."""
        now = timezone.now()

        generated.preview_status = (
            TrackGeneratedAudio.ProcessingStatus.BUILDING
        )
        generated.preview_error = ''
        generated.preview_started_at = now

        generated.stream_status = TrackGeneratedAudio.ProcessingStatus.BUILDING
        generated.stream_error = ''
        generated.stream_started_at = now

        generated.save(
            update_fields=(
                'preview_status',
                'preview_error',
                'preview_started_at',
                'stream_status',
                'stream_error',
                'stream_started_at',
            ),
        )

    @staticmethod
    def _mark_processing_failed(
        *,
        generated: TrackGeneratedAudio,
        error: Exception,
    ) -> None:
        """Отмечает обе производные версии как неуспешно обработанные."""
        error_message = str(error)[:2000]

        generated.preview_status = TrackGeneratedAudio.ProcessingStatus.FAILED
        generated.preview_error = error_message

        generated.stream_status = TrackGeneratedAudio.ProcessingStatus.FAILED
        generated.stream_error = error_message

        generated.save(
            update_fields=(
                'preview_status',
                'preview_error',
                'stream_status',
                'stream_error',
            ),
        )

    @staticmethod
    def _delete_storage_file(storage, file_name: str) -> None:
        """Удаляет устаревший файл из storage без срыва обработки."""
        if not file_name:
            return

        try:
            storage.delete(file_name)
        except Exception:
            logger.exception(
                'Не удалось удалить устаревший сгенерированный файл: %s',
                file_name,
            )

    @staticmethod
    def _raise_storage_error(error: Exception) -> None:
        """Преобразует временные ошибки storage в доменное исключение."""
        if isinstance(
            error,
            (
                ConnectionError,
                TimeoutError,
                socket.timeout,
                URLError,
            ),
        ):
            raise TemporaryAudioStorageError(
                'Временная ошибка доступа к файловому хранилищу.',
            ) from error

        raise error
