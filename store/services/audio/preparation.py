"""Подготовка производных аудиофайлов трека."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from django.core.files import File
from django.utils import timezone

from store.models import Track, TrackGeneratedAudio
from store.services.audio.processing import AudioProcessingService


class TrackAudioPreparationService:
    """Подготавливает preview и stream для трека."""

    @classmethod
    def prepare(cls, track_id: int) -> None:
        """Создаёт производные аудиофайлы для указанного трека."""
        try:
            track = Track.objects.get(pk=track_id)
        except Track.DoesNotExist:
            return

        generated, _ = TrackGeneratedAudio.objects.get_or_create(
            track=track,
        )

        cls._mark_processing_started(generated)

        try:
            with tempfile.TemporaryDirectory(
                prefix=f'track-{track.pk}-',
            ) as temporary_directory:
                workdir = Path(temporary_directory)

                source_path = cls._download_source_file(
                    track=track,
                    workdir=workdir,
                )

                metadata = AudioProcessingService.probe_metadata(
                    source_path,
                )

                track.duration = metadata.duration
                track.save(update_fields=('duration',))

                stream_path = workdir / 'stream.mp3'
                preview_path = workdir / 'preview.mp3'

                errors = []

                try:
                    cls._prepare_stream(
                        generated=generated,
                        source_path=source_path,
                        target_path=stream_path,
                    )
                except Exception as error:
                    errors.append(error)

                try:
                    cls._prepare_preview(
                        generated=generated,
                        source_path=source_path,
                        target_path=preview_path,
                        source_duration=metadata.duration,
                    )
                except Exception as error:
                    errors.append(error)

        except Exception as error:
            cls._mark_processing_failed(
                generated=generated,
                error=error,
            )
            raise

        if errors:
            raise errors[0]

    @staticmethod
    def _download_source_file(
        *,
        track: Track,
        workdir: Path,
    ) -> Path:
        """Скачивает исходный аудиофайл во временную директорию."""
        suffix = Path(track.audio_file.name).suffix.lower()
        source_path = workdir / f'original{suffix}'

        with track.audio_file.open('rb') as source_file:
            with source_path.open('wb') as target_file:
                shutil.copyfileobj(source_file, target_file)

        return source_path

    @classmethod
    def _prepare_stream(
        cls,
        *,
        generated: TrackGeneratedAudio,
        source_path: Path,
        target_path: Path,
    ) -> None:
        """Создаёт и сохраняет stream-файл."""
        try:
            AudioProcessingService.create_stream(
                source_path=source_path,
                target_path=target_path,
            )

            with target_path.open('rb') as stream_file:
                generated.stream_file.save(
                    'stream.mp3',
                    File(stream_file),
                    save=False,
                )

            generated.stream_status = (
                TrackGeneratedAudio.ProcessingStatus.READY
            )
            generated.stream_error = ''
            generated.save(
                update_fields=(
                    'stream_file',
                    'stream_status',
                    'stream_error',
                ),
            )
        except Exception as error:
            generated.stream_status = (
                TrackGeneratedAudio.ProcessingStatus.FAILED
            )
            generated.stream_error = str(error)[:2000]
            generated.save(
                update_fields=(
                    'stream_status',
                    'stream_error',
                ),
            )
            raise

    @classmethod
    def _prepare_preview(
        cls,
        *,
        generated: TrackGeneratedAudio,
        source_path: Path,
        target_path: Path,
        source_duration: int,
    ) -> None:
        """Создаёт и сохраняет preview-файл."""
        try:
            preview_duration = AudioProcessingService.create_preview(
                source_path=source_path,
                target_path=target_path,
                source_duration=source_duration,
            )

            with target_path.open('rb') as preview_file:
                generated.preview_file.save(
                    'preview.mp3',
                    File(preview_file),
                    save=False,
                )

            generated.preview_duration = preview_duration
            generated.preview_status = (
                TrackGeneratedAudio.ProcessingStatus.READY
            )
            generated.preview_error = ''
            generated.save(
                update_fields=(
                    'preview_file',
                    'preview_duration',
                    'preview_status',
                    'preview_error',
                ),
            )
        except Exception as error:
            generated.preview_status = (
                TrackGeneratedAudio.ProcessingStatus.FAILED
            )
            generated.preview_error = str(error)[:2000]
            generated.save(
                update_fields=(
                    'preview_status',
                    'preview_error',
                ),
            )
            raise

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
