"""Подготовка производных аудиофайлов через ffmpeg."""

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from store.constants import (
    AUDIO_PROCESSING_TIMEOUT,
    PREVIEW_BITRATE,
    PREVIEW_CROSSFADE_DURATION,
    PREVIEW_DURATION,
    PREVIEW_SEGMENT_DURATION,
    STREAM_BITRATE,
)
from store.exceptions import AudioProcessingError


@dataclass(frozen=True)
class AudioMetadata:
    """Метаданные аудиофайла."""

    duration: int


class AudioProcessingService:
    """Подготавливает stream и preview из исходного аудиофайла."""

    @classmethod
    def probe_metadata(cls, source_path: Path) -> AudioMetadata:
        """Возвращает метаданные исходного аудиофайла."""
        command = (
            settings.FFPROBE_BINARY,
            '-v',
            'error',
            '-show_entries',
            'format=duration',
            '-of',
            'json',
            str(source_path),
        )

        result = cls._run(command)

        try:
            payload = json.loads(result.stdout)
            duration = float(payload['format']['duration'])
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise AudioProcessingError(
                'Не удалось определить длительность аудиофайла.',
            ) from error

        if not math.isfinite(duration) or duration <= 0:
            raise AudioProcessingError(
                'Длительность аудиофайла должна быть больше нуля.',
            )

        return AudioMetadata(
            duration=math.ceil(duration),
        )

    @classmethod
    def create_stream(
        cls,
        *,
        source_path: Path,
        target_path: Path,
    ) -> None:
        """Создаёт полную версию трека для потокового воспроизведения."""
        command = (
            settings.FFMPEG_BINARY,
            '-v',
            'error',
            '-y',
            '-i',
            str(source_path),
            '-map',
            '0:a:0',
            '-vn',
            '-map_metadata',
            '-1',
            '-c:a',
            'libmp3lame',
            '-b:a',
            STREAM_BITRATE,
            str(target_path),
        )

        cls._run(command)

    @classmethod
    def create_preview(
        cls,
        *,
        source_path: Path,
        target_path: Path,
        source_duration: int,
    ) -> int:
        """Создаёт preview из начала и середины трека."""
        if cls._should_use_whole_track(source_duration):
            cls._create_full_track_preview(
                source_path=source_path,
                target_path=target_path,
            )
            return source_duration

        second_segment_start = cls._get_remaining_segment_start(
            source_duration=source_duration,
        )

        filter_complex = (
            '[0:a]atrim=start=0:duration='
            f'{PREVIEW_SEGMENT_DURATION},'
            'asetpts=N/SR/TB[first];'
            '[0:a]atrim=start='
            f'{second_segment_start}:duration={PREVIEW_SEGMENT_DURATION},'
            'asetpts=N/SR/TB[second];'
            '[first][second]acrossfade=d='
            f'{PREVIEW_CROSSFADE_DURATION}'
            ':c1=tri:c2=tri[audio]'
        )

        command = (
            settings.FFMPEG_BINARY,
            '-v',
            'error',
            '-y',
            '-i',
            str(source_path),
            '-filter_complex',
            filter_complex,
            '-map',
            '[audio]',
            '-vn',
            '-map_metadata',
            '-1',
            '-c:a',
            'libmp3lame',
            '-b:a',
            PREVIEW_BITRATE,
            str(target_path),
        )

        cls._run(command)

        return PREVIEW_DURATION

    @classmethod
    def _create_full_track_preview(
        cls,
        *,
        source_path: Path,
        target_path: Path,
    ) -> None:
        """Создаёт preview из полного короткого трека."""
        command = (
            settings.FFMPEG_BINARY,
            '-v',
            'error',
            '-y',
            '-i',
            str(source_path),
            '-map',
            '0:a:0',
            '-vn',
            '-map_metadata',
            '-1',
            '-c:a',
            'libmp3lame',
            '-b:a',
            PREVIEW_BITRATE,
            str(target_path),
        )

        cls._run(command)

    @staticmethod
    def _should_use_whole_track(source_duration: int) -> bool:
        """Проверяет, нужно ли использовать трек целиком для preview."""
        return source_duration <= PREVIEW_SEGMENT_DURATION * 2

    @staticmethod
    def _get_remaining_segment_start(source_duration: int) -> float:
        """Возвращает начало фрагмента из оставшейся части трека."""
        remaining_start = PREVIEW_SEGMENT_DURATION
        remaining_duration = source_duration - remaining_start

        return (
            remaining_start
            + (remaining_duration - PREVIEW_SEGMENT_DURATION) / 2
        )

    @staticmethod
    def _run(command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        """Запускает внешнюю команду и оборачивает ошибки ffmpeg."""
        try:
            return subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=AUDIO_PROCESSING_TIMEOUT,
            )
        except subprocess.TimeoutExpired as error:
            raise AudioProcessingError(
                'Превышено время подготовки аудиофайла.',
            ) from error
        except FileNotFoundError as error:
            raise AudioProcessingError(
                'ffmpeg или ffprobe не найдены в системе.',
            ) from error
        except subprocess.CalledProcessError as error:
            error_output = error.stderr.strip()

            raise AudioProcessingError(
                f'Не удалось обработать аудиофайл: {error_output[-1000:]}',
            ) from error
