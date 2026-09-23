"""Возобновляемое подключение аудио к импортированным Track."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import DatabaseError, transaction
from django.utils import timezone

from catalog_migration.services.catalog_bundle import (
    bundle_root,
    bundle_version,
    mapping_version,
)
from catalog_migration.services.catalog_migration_preflight import (
    CatalogMigrationPreflight,
    PreflightResult,
)

from store.models import (
    Album,
    CatalogMigrationAudioState,
    CatalogMigrationMapping,
    Track,
    TrackGeneratedAudio,
    TrackUpload,
)
from store.services.audio import TrackGeneratedAudioScheduler
from store.services.track_upload import (
    TrackUploadService,
    TrackUploadStorageError,
    TrackUploadStorageService,
)

JsonObject = dict[str, Any]
DEFAULT_SOURCE_PREFIX = 'migration/v1.3'


class CatalogAudioImportError(RuntimeError):
    """Безопасная обезличенная ошибка импорта аудио."""


@dataclass(frozen=True)
class AudioCandidate:
    """Проверенные связи bundle для одного исходного аудио."""

    entity_id: str
    mapping: CatalogMigrationMapping
    track: Track
    asset_id: str
    bundle_path: str
    filename: str
    source_key: str
    sha256: str
    size: int
    staging_key: str
    original_key: str


@dataclass(frozen=True)
class CatalogAudioImportResult:
    """Сводка без имён артистов, треков и приватных ключей."""

    preflight: PreflightResult
    selected: int
    would_start: int
    queued: int
    ready: int
    processing: int
    failed: int
    dry_run: bool

    def render(self) -> str:
        """Возвращает компактный итог запуска."""
        mode = 'DRY-RUN' if self.dry_run else 'PASS'
        return (
            f'AUDIO IMPORT {mode}\nselected={self.selected} '
            f'would_start={self.would_start} queued={self.queued} '
            f'ready={self.ready} processing={self.processing} '
            f'failed={self.failed}'
        )


class CatalogAudioImporter:
    """Подключает immutable S3 source через существующий REPLACE upload."""

    def __init__(
        self,
        package_root: Path | str,
        *,
        dry_run: bool = False,
        track_entity_id: str | None = None,
        retry_errors: bool = False,
        source_prefix: str = DEFAULT_SOURCE_PREFIX,
        progress_callback: Callable[[int, int], None] | None = None,
    ):
        """Настраивает пакет, ограничение трека и режим повтора."""
        self.package_root = Path(package_root).expanduser()
        self.bundle_version = bundle_version(self.package_root)
        self.mapping_version = mapping_version(self.package_root)
        self.bundle_root = bundle_root(self.package_root)
        self.dry_run = dry_run
        self.track_entity_id = track_entity_id
        self.retry_errors = retry_errors
        self.source_prefix = source_prefix.strip('/')
        if (
            self.bundle_version == '2.0'
            and source_prefix == DEFAULT_SOURCE_PREFIX
        ):
            self.source_prefix = 'migration-v2'
        self.progress_callback = progress_callback

    def run(self) -> CatalogAudioImportResult:
        """Проверяет весь выбранный набор до первого изменения."""
        preflight = CatalogMigrationPreflight(self.package_root).run()
        if not preflight.passed:
            raise CatalogAudioImportError(preflight.render())

        config = self._read_object(self.package_root / 'import_config.json')
        if not config['enabled']['tracks']:
            return self._result(preflight, selected=0)

        candidates = self._load_candidates(config)
        self._validate_existing_states(candidates)
        classified = {
            entity_id: self._classify(candidate)
            for entity_id, candidate in candidates.items()
        }

        blocked = sorted(
            entity_id
            for entity_id, status in classified.items()
            if status == 'failed' and not self.retry_errors
        )
        if blocked:
            raise CatalogAudioImportError(
                'Есть ошибочные состояния; используйте --retry-errors '
                'после устранения причины; '
                f'entity_id={",".join(blocked)}',
            )

        would_start = sum(
            status in {'new', 'retry'} for status in classified.values()
        )
        self._report_progress(0, len(candidates))
        if self.dry_run:
            return self._result(
                preflight,
                selected=len(candidates),
                would_start=would_start,
                ready=self._count(classified, 'ready'),
                processing=self._count(classified, 'processing'),
            )
        queued = 0
        failed = 0
        failed_entity_ids = []
        for processed, entity_id in enumerate(sorted(candidates), start=1):
            status = classified[entity_id]
            candidate = candidates[entity_id]
            if status in {'ready', 'processing'}:
                self._synchronise_state(candidate, status)
                self._report_progress(processed, len(candidates))
                continue
            try:
                queued += int(
                    self._start_or_resume(
                        candidate,
                        retry=status == 'retry',
                    ),
                )
            except (
                DatabaseError,
                TrackUploadStorageError,
                ValidationError,
            ) as error:
                self._mark_failed(candidate, error)
                failed += 1
                failed_entity_ids.append(entity_id)
            self._report_progress(processed, len(candidates))

        if failed:
            raise CatalogAudioImportError(
                'Не удалось поставить аудио в обработку; '
                f'failed={failed}; '
                f'entity_id={",".join(failed_entity_ids)}',
            )
        refreshed = {
            entity_id: self._classify(candidate)
            for entity_id, candidate in candidates.items()
        }
        return self._result(
            preflight,
            selected=len(candidates),
            queued=queued,
            ready=self._count(refreshed, 'ready'),
            processing=self._count(refreshed, 'processing'),
        )

    def _report_progress(self, processed: int, total: int) -> None:
        if self.progress_callback is not None:
            self.progress_callback(processed, total)

    def _load_candidates(
        self,
        config: JsonObject,
    ) -> dict[str, AudioCandidate]:
        codes = self._read_object(self.package_root / 'artist_codes.json')
        profile_ids = {
            row['entity_id']
            for row in codes['artists']
            if row['code'] in set(config['artist_code_whitelist'])
        }
        releases = self._read_array(
            self.bundle_root / 'data' / 'releases.json',
        )
        release_ids = {
            row['entity_id']
            for row in releases
            if row['profile_id'] in profile_ids
        }
        tracks = {
            row['entity_id']: row
            for row in self._read_array(
                self.bundle_root / 'data' / 'tracks.json',
            )
            if row['release_id'] in release_ids
        }
        # Explicitly unavailable v2 originals remain draft tracks,
        # not fake assets.
        if self.bundle_version == '2.0':
            tracks = {
                key: row
                for key, row in tracks.items()
                if not (
                    row.get('audio_asset_id') is None
                    and row.get('audio_status') == 'MISSING'
                )
            }
        if self.track_entity_id is not None:
            if self.track_entity_id not in tracks:
                raise CatalogAudioImportError(
                    'Трек не входит в выбранный whitelist; '
                    f'entity_id={self.track_entity_id}',
                )
            tracks = {self.track_entity_id: tracks[self.track_entity_id]}

        assets = {
            row['asset_id']: row
            for row in self._read_object(
                self.bundle_root / 'media' / 'manifests' / 'audio.json',
            )['assets']
        }
        mappings = {
            row.source_entity_id: row
            for row in CatalogMigrationMapping.objects.filter(
                bundle_version=self.mapping_version,
                entity_type=CatalogMigrationMapping.EntityType.TRACK,
                source_entity_id__in=tracks,
            )
        }
        targets = Track.objects.select_related('album').in_bulk(
            mapping.django_pk for mapping in mappings.values()
        )
        release_mappings = {
            row.source_entity_id: row
            for row in CatalogMigrationMapping.objects.filter(
                bundle_version=self.mapping_version,
                entity_type=CatalogMigrationMapping.EntityType.RELEASE,
                source_entity_id__in=release_ids,
            )
        }
        albums = Album.objects.in_bulk(
            mapping.django_pk for mapping in release_mappings.values()
        )
        errors = []
        candidates = {}
        staging_version = 'v2' if self.bundle_version == '2.0' else 'v1.3'
        for entity_id, row in tracks.items():
            mapping = mappings.get(entity_id)
            asset = assets.get(row.get('audio_asset_id'))
            if mapping is None:
                errors.append(
                    f'TRACK mapping отсутствует; entity_id={entity_id}',
                )
                continue
            track = targets.get(mapping.django_pk)
            if track is None:
                errors.append(f'TRACK mapping осиротел; entity_id={entity_id}')
                continue
            release_id = row.get('release_id')
            release_mapping = release_mappings.get(release_id)
            if (
                release_mapping is None
                or release_mapping.django_pk not in albums
                or track.album_id != release_mapping.django_pk
            ):
                errors.append(
                    f'TRACK mapping конфликтует с RELEASE mapping; '
                    f'entity_id={entity_id}',
                )
                continue
            if not self._valid_asset(
                asset,
                entity_id,
                row.get('audio_asset_id'),
            ):
                errors.append(
                    f'Некорректный audio asset; entity_id={entity_id}',
                )
                continue
            digest = hashlib.sha256(
                f'{self.mapping_version}:{entity_id}:{asset["asset_id"]}'.encode(),
            ).hexdigest()[:24]
            suffix = Path(asset['original_filename']).suffix.lower()
            filename = f'{digest}{suffix}'
            candidates[entity_id] = AudioCandidate(
                entity_id=entity_id,
                mapping=mapping,
                track=track,
                asset_id=asset['asset_id'],
                bundle_path=asset['bundle_path'],
                filename=filename,
                source_key=(
                    f'{self.source_prefix}/{self.bundle_root.name}/'
                    f'{asset["bundle_path"].lstrip("/")}'
                ),
                sha256=asset['sha256'],
                size=asset['size'],
                staging_key=(
                    f'staging/catalog-migration/{staging_version}/'
                    f'{digest}/{filename}'
                ),
                original_key=(
                    f'albums/{track.album_id}/tracks/original/{filename}'
                ),
            )
        if errors:
            raise CatalogAudioImportError('\n'.join(sorted(errors)))
        return candidates

    @staticmethod
    def _valid_asset(asset: Any, entity_id: str, asset_id: Any) -> bool:
        return bool(
            isinstance(asset, dict)
            and asset.get('asset_id') == asset_id
            and asset.get('entity_id') == entity_id
            and asset.get('entity_type') == 'track'
            and asset.get('role') == 'audio_original'
            and isinstance(asset.get('bundle_path'), str)
            and isinstance(asset.get('original_filename'), str)
            and isinstance(asset.get('size'), int)
            and asset['size'] > 0
            and isinstance(asset.get('sha256'), str)
            and len(asset['sha256']) == 64
            and all(
                char in '0123456789abcdefABCDEF' for char in asset['sha256']
            ),
        )

    def _validate_existing_states(
        self,
        candidates: dict[str, AudioCandidate],
    ) -> None:
        states = CatalogMigrationAudioState.objects.filter(
            mapping_id__in=(
                candidate.mapping.pk for candidate in candidates.values()
            ),
        ).select_related('upload')
        by_mapping = {state.mapping_id: state for state in states}
        conflicts = []
        for candidate in candidates.values():
            state = by_mapping.get(candidate.mapping.pk)
            if state is None:
                if candidate.track.audio_file.name:
                    conflicts.append(candidate.entity_id)
                continue
            expected = (
                state.track_id == candidate.track.pk
                and state.asset_id == candidate.asset_id
                and state.source_key == candidate.source_key
                and state.source_sha256.lower() == candidate.sha256.lower()
                and state.expected_size == candidate.size
                and state.staging_key == candidate.staging_key
                and state.original_key == candidate.original_key
            )
            if state.upload_id is not None:
                expected = expected and (
                    state.upload.track_id == candidate.track.pk
                    and state.upload.purpose == TrackUpload.Purpose.REPLACE
                    and state.upload.staging_key == candidate.staging_key
                )
                if state.upload.status == TrackUpload.Status.COMPLETED:
                    expected = expected and (
                        candidate.track.audio_file.name
                        == candidate.original_key
                    )
                else:
                    expected = expected and not candidate.track.audio_file.name
            if not expected:
                conflicts.append(candidate.entity_id)
        if conflicts:
            raise CatalogAudioImportError(
                'Состояние аудио конфликтует с bundle/mapping; '
                f'entity_id={",".join(sorted(conflicts))}',
            )

    def _classify(self, candidate: AudioCandidate) -> str:
        state = (
            CatalogMigrationAudioState.objects
            .filter(
                mapping=candidate.mapping,
            )
            .select_related('upload')
            .first()
        )
        if state is None:
            return 'new'
        generated = TrackGeneratedAudio.objects.filter(
            track=candidate.track,
        ).first()
        if self._is_ready(candidate, generated):
            return 'ready'
        if generated is not None:
            statuses = {generated.preview_status, generated.stream_status}
            if TrackGeneratedAudio.ProcessingStatus.FAILED in statuses:
                return 'retry' if self.retry_errors else 'failed'
            if statuses & {
                TrackGeneratedAudio.ProcessingStatus.PENDING,
                TrackGeneratedAudio.ProcessingStatus.BUILDING,
            }:
                return 'processing'
        if state.status == CatalogMigrationAudioState.Status.FAILED:
            return 'retry' if self.retry_errors else 'failed'
        if state.status in {
            CatalogMigrationAudioState.Status.COPYING,
            CatalogMigrationAudioState.Status.QUEUED,
            CatalogMigrationAudioState.Status.PROCESSING,
        }:
            return 'processing'
        if (
            state.upload_id
            and state.upload.status == TrackUpload.Status.COMPLETED
        ):
            return 'retry'
        return 'new'

    @classmethod
    def _generated_is_retryable(
        cls,
        state: CatalogMigrationAudioState,
        generated: TrackGeneratedAudio | None,
    ) -> bool:
        """Повторно проверяет ошибку generated под блокировкой строки."""
        if generated is None:
            return False
        statuses = {generated.preview_status, generated.stream_status}
        return TrackGeneratedAudio.ProcessingStatus.FAILED in statuses

    @staticmethod
    def _is_ready(candidate: AudioCandidate, generated) -> bool:
        return bool(
            candidate.track.audio_file.name == candidate.original_key
            and candidate.track.duration is not None
            and generated is not None
            and generated.preview_status
            == TrackGeneratedAudio.ProcessingStatus.READY
            and generated.stream_status
            == TrackGeneratedAudio.ProcessingStatus.READY
            and generated.preview_file.name
            and generated.stream_file.name,
        )

    def _start_or_resume(
        self,
        candidate: AudioCandidate,
        *,
        retry: bool,
    ) -> bool:
        state = self._claim_state(candidate, retry=retry)
        if state is None:
            return False
        upload = self._ensure_upload(state, candidate)

        if upload.status != TrackUpload.Status.COMPLETED:
            if upload.status != TrackUpload.Status.UPLOADED:
                if settings.USE_S3_MEDIA:
                    TrackUploadStorageService.copy_s3_source_to_staging(
                        upload=upload,
                        source_key=candidate.source_key,
                        expected_sha256=candidate.sha256,
                    )
                else:
                    self._copy_local_source_to_staging(upload, candidate)
            TrackUploadStorageService.complete(
                upload=upload,
                final_key=candidate.original_key,
                schedule_audio=False,
                schedule_archive=False,
            )

        self._mark_queued(state, candidate.track, retry=retry)
        try:
            TrackGeneratedAudioScheduler.enqueue(candidate.track.pk)
        except Exception as error:
            self._mark_failed(candidate, error)
            if retry:
                self._mark_generated_failed(candidate.track, error)
            raise CatalogAudioImportError(
                'Не удалось поставить задачу Celery; '
                f'entity_id={candidate.entity_id}',
            ) from error
        return True

    def _copy_local_source_to_staging(
        self,
        upload: TrackUpload,
        candidate: AudioCandidate,
    ) -> None:
        """Проверяет package source и передаёт его штатному local upload."""
        bundle_path = PurePosixPath(candidate.bundle_path)
        if bundle_path.is_absolute() or '..' in bundle_path.parts:
            raise TrackUploadStorageError(
                'Некорректный локальный путь исходного аудиофайла.',
            )
        source_path = self.bundle_root.joinpath(*bundle_path.parts)
        try:
            if source_path.stat().st_size != candidate.size:
                raise TrackUploadStorageError(
                    'Размер исходного аудиофайла не совпадает с manifest.',
                )
            digest = hashlib.sha256()
            with source_path.open('rb') as source:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                if digest.hexdigest().lower() != candidate.sha256.lower():
                    raise TrackUploadStorageError(
                        'SHA-256 исходного аудиофайла не совпадает '
                        'с manifest.',
                    )
                source.seek(0)
                TrackUploadService.receive_local_file(
                    upload=upload,
                    uploaded_file=File(source, name=candidate.filename),
                )
        except OSError as error:
            raise TrackUploadStorageError(
                'Не удалось прочитать локальный исходный аудиофайл.',
            ) from error

    @staticmethod
    @transaction.atomic
    def _mark_queued(
        state: CatalogMigrationAudioState,
        track: Track,
        *,
        retry: bool,
    ) -> None:
        """Одной фиксацией публикует очередь и сбрасывает старый FAILED."""
        state = CatalogMigrationAudioState.objects.select_for_update().get(
            pk=state.pk,
        )
        state.status = CatalogMigrationAudioState.Status.QUEUED
        state.error = ''
        state.queued_at = timezone.now()
        state.save(
            update_fields=('status', 'error', 'queued_at', 'updated_at'),
        )
        if not retry:
            return
        generated = (
            TrackGeneratedAudio.objects
            .select_for_update()
            .filter(track=track)
            .first()
        )
        if generated is None:
            return
        generated.preview_status = TrackGeneratedAudio.ProcessingStatus.PENDING
        generated.preview_error = ''
        generated.preview_started_at = None
        generated.stream_status = TrackGeneratedAudio.ProcessingStatus.PENDING
        generated.stream_error = ''
        generated.stream_started_at = None
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

    @classmethod
    @transaction.atomic
    def _claim_state(
        cls,
        candidate: AudioCandidate,
        *,
        retry: bool,
    ) -> CatalogMigrationAudioState | None:
        """Атомарно исключает параллельный запуск того же Track."""
        state, _ = (
            CatalogMigrationAudioState.objects.select_for_update().get_or_create(
                mapping=candidate.mapping,
                defaults={
                    'track': candidate.track,
                    'asset_id': candidate.asset_id,
                    'source_key': candidate.source_key,
                    'source_sha256': candidate.sha256,
                    'expected_size': candidate.size,
                    'staging_key': candidate.staging_key,
                    'original_key': candidate.original_key,
                },
            )
        )
        if state.status in {
            CatalogMigrationAudioState.Status.COPYING,
            CatalogMigrationAudioState.Status.QUEUED,
            CatalogMigrationAudioState.Status.PROCESSING,
        }:
            if state.status == CatalogMigrationAudioState.Status.COPYING:
                return None
            generated = (
                TrackGeneratedAudio.objects
                .select_for_update()
                .filter(track=candidate.track)
                .first()
            )
            if not retry or not cls._generated_is_retryable(
                state,
                generated,
            ):
                return None
        state.status = CatalogMigrationAudioState.Status.COPYING
        state.error = ''
        state.save(update_fields=('status', 'error', 'updated_at'))
        return state

    @staticmethod
    @transaction.atomic
    def _ensure_upload(
        state: CatalogMigrationAudioState,
        candidate: AudioCandidate,
    ) -> TrackUpload:
        state = CatalogMigrationAudioState.objects.select_for_update().get(
            pk=state.pk,
        )
        if state.upload_id is not None:
            return TrackUpload.objects.get(pk=state.upload_id)
        upload = TrackUploadService.create_replacement_upload(
            track=candidate.track,
            filename=candidate.filename,
            size=candidate.size,
            staging_key=candidate.staging_key,
        )
        state.upload = upload
        state.save(update_fields=('upload', 'updated_at'))
        return upload

    def _synchronise_state(
        self,
        candidate: AudioCandidate,
        status: str,
    ) -> None:
        state = CatalogMigrationAudioState.objects.filter(
            mapping=candidate.mapping,
        ).first()
        if state is None:
            return
        generated = TrackGeneratedAudio.objects.filter(
            track=candidate.track,
        ).first()
        state.status = (
            CatalogMigrationAudioState.Status.READY
            if status == 'ready'
            else CatalogMigrationAudioState.Status.PROCESSING
        )
        if status == 'ready' and generated is not None:
            state.preview_key = generated.preview_file.name
            state.stream_key = generated.stream_file.name
        state.save(
            update_fields=(
                'status',
                'preview_key',
                'stream_key',
                'updated_at',
            ),
        )

    @staticmethod
    def _mark_failed(candidate: AudioCandidate, error: Exception) -> None:
        CatalogMigrationAudioState.objects.filter(
            mapping=candidate.mapping,
        ).update(
            status=CatalogMigrationAudioState.Status.FAILED,
            error=type(error).__name__[:2000],
            updated_at=timezone.now(),
        )

    @staticmethod
    def _mark_generated_failed(track: Track, error: Exception) -> None:
        """Возвращает сброшенный retry в явный FAILED при ошибке broker."""
        TrackGeneratedAudio.objects.filter(track=track).update(
            preview_status=TrackGeneratedAudio.ProcessingStatus.FAILED,
            preview_error=type(error).__name__[:2000],
            stream_status=TrackGeneratedAudio.ProcessingStatus.FAILED,
            stream_error=type(error).__name__[:2000],
        )

    @staticmethod
    def _count(classified: dict[str, str], status: str) -> int:
        return sum(value == status for value in classified.values())

    def _result(
        self,
        preflight: PreflightResult,
        **kwargs,
    ) -> CatalogAudioImportResult:
        return CatalogAudioImportResult(
            preflight=preflight,
            selected=kwargs.get('selected', 0),
            would_start=kwargs.get('would_start', 0),
            queued=kwargs.get('queued', 0),
            ready=kwargs.get('ready', 0),
            processing=kwargs.get('processing', 0),
            failed=kwargs.get('failed', 0),
            dry_run=self.dry_run,
        )

    @staticmethod
    def _read_object(path: Path) -> JsonObject:
        with path.open(encoding='utf-8') as file:
            value = json.load(file)
        if not isinstance(value, dict):
            raise CatalogAudioImportError(f'Ожидался JSON object: {path.name}')
        return value

    @staticmethod
    def _read_array(path: Path) -> list[JsonObject]:
        with path.open(encoding='utf-8') as file:
            value = json.load(file)
        if not isinstance(value, list):
            raise CatalogAudioImportError(f'Ожидался JSON array: {path.name}')
        return value
