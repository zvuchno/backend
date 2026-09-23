"""Тесты возобновляемого импорта оригиналов Track."""

import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from threading import Barrier, Event
from typing import Any
from unittest.mock import patch

import pytest
from django.db import IntegrityError, close_old_connections, connection
from django.utils import timezone

from catalog_migration.services.catalog_audio_import import (
    AudioCandidate,
    CatalogAudioImportError,
    CatalogAudioImportResult,
    CatalogAudioImporter,
)
from catalog_migration.services.catalog_bundle import (
    bundle_root,
    mapping_version,
)
from catalog_migration.services.catalog_profile_import import (
    CatalogProfileImporter,
)
from catalog_migration.services.catalog_release_import import (
    CatalogReleaseImporter,
)
from catalog_migration.services.catalog_track_import import (
    CatalogTrackImporter,
)
from catalog_migration.tests.test_catalog_migration_preflight import (
    BUNDLE_DIRECTORY,
    _load,
    _make_package,
    _write_json,
)
from catalog_migration.tests.test_catalog_track_import import (
    _create_album_mapping,
    _set_whitelist,
)
from catalog_migration.tests.v2_package import v2_package

from store.models import (
    CatalogMigrationAudioState,
    Product,
    Track,
    TrackGeneratedAudio,
    TrackUpload,
)
from store.services.track_upload import TrackUploadStorageService


class FakeS3Client:
    """Минимальный fake без сетевого доступа."""

    def __init__(self, *, source_key: str, content: bytes, checksum=True):
        """Сохраняет единственный исходный объект и журнал операций."""
        self.source_key = source_key
        self.content = content
        self.checksum = checksum
        self.copies = []
        self.deletes = []

    def head_object(self, **kwargs):
        key = kwargs['Key']
        if key == self.source_key:
            result = {'ContentLength': len(self.content), 'ETag': 'not-sha256'}
            if self.checksum:
                result['ChecksumSHA256'] = base64.b64encode(
                    hashlib.sha256(self.content).digest(),
                ).decode()
            return result
        return {'ContentLength': len(self.content)}

    def copy_object(self, **kwargs):
        self.copies.append(kwargs)
        return {}

    def get_object(self, **kwargs):
        assert kwargs['Key'] == self.source_key
        return {'Body': BytesIO(self.content)}

    def delete_object(self, **kwargs):
        self.deletes.append(kwargs)
        return {}


@pytest.fixture(autouse=True)
def _fake_s3_settings(settings) -> None:
    settings.AWS_PRIVATE_STORAGE_BUCKET_NAME = 'fake-private-bucket'
    settings.MEDIA_LOCATION = 'private'


def _prepare_audio_package(tmp_path: Path) -> tuple[Path, Track, str, bytes]:
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    content = b'canonical source audio'
    digest = hashlib.sha256(content).hexdigest()
    manifest = {
        'assets': [
            {
                'asset_id': 'audio-00',
                'bundle_path': 'media/audio/originals/audio-00.wav',
                'entity_id': 'track-00',
                'entity_type': 'track',
                'original_filename': 'original.wav',
                'role': 'audio_original',
                'sha256': digest,
                'size': len(content),
            },
        ],
    }
    _write_json(
        package / BUNDLE_DIRECTORY / 'media' / 'manifests' / 'audio.json',
        manifest,
    )
    _create_album_mapping(package, 0)
    CatalogTrackImporter(package).run()
    track = Track.objects.get()
    source_key = (
        'migration/v1.3/zvuchno-migration-bundle-v1.3/'
        'media/audio/originals/audio-00.wav'
    )
    return package, track, source_key, content


@pytest.mark.django_db(transaction=True)
def test_import_uses_replace_and_never_deletes_source(
    tmp_path,
    settings,
    django_capture_on_commit_callbacks,
):
    """REPLACE сохраняет Track и никогда не удаляет package source."""
    package, track, source_key, content = _prepare_audio_package(tmp_path)
    settings.USE_S3_MEDIA = True
    client = FakeS3Client(source_key=source_key, content=content)

    with (
        patch.object(
            TrackUploadStorageService,
            '_get_s3_client',
            return_value=client,
        ),
        patch(
            'catalog_migration.services.catalog_audio_import.'
            'TrackGeneratedAudioScheduler.enqueue',
        ) as enqueue,
        django_capture_on_commit_callbacks(execute=True),
    ):
        result = CatalogAudioImporter(package).run()

    track.refresh_from_db()
    state = CatalogMigrationAudioState.objects.get()
    upload = TrackUpload.objects.get()
    assert result.queued == 1
    assert upload.purpose == TrackUpload.Purpose.REPLACE
    assert track.pk == state.track_id
    assert track.position == 1
    assert track.audio_file.name == state.original_key
    assert Product.objects.count() == 0
    assert len(client.copies) == 2
    assert all(item['Key'] != source_key for item in client.deletes)
    assert all(
        item['CopySource']['Key'] == source_key for item in client.copies[:1]
    )
    enqueue.assert_called_once_with(track.pk)


@pytest.mark.django_db(transaction=True)
def test_local_import_uses_track_upload_without_s3(
    tmp_path,
    settings,
    django_capture_on_commit_callbacks,
):
    """Локальный source проходит через штатные staging и complete."""
    package, track, _, content = _prepare_audio_package(tmp_path)
    settings.USE_S3_MEDIA = False
    source_path = (
        package / BUNDLE_DIRECTORY / 'media/audio/originals/audio-00.wav'
    )
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(content)

    with (
        patch.object(
            TrackUploadStorageService,
            '_get_s3_client',
            side_effect=AssertionError('S3 must not be used'),
        ) as get_s3_client,
        patch(
            'catalog_migration.services.catalog_audio_import.'
            'TrackGeneratedAudioScheduler.enqueue',
        ) as enqueue,
        django_capture_on_commit_callbacks(execute=True),
    ):
        result = CatalogAudioImporter(package).run()

    track.refresh_from_db()
    upload = TrackUpload.objects.get()
    assert result.queued == 1
    assert upload.status == TrackUpload.Status.COMPLETED
    assert upload.purpose == TrackUpload.Purpose.REPLACE
    assert track.position == 1
    assert track.audio_file.storage.exists(track.audio_file.name)
    with track.audio_file.open('rb') as imported:
        assert imported.read() == content
    assert source_path.read_bytes() == content
    assert not track.audio_file.storage.exists(upload.staging_key)
    get_s3_client.assert_not_called()
    enqueue.assert_called_once_with(track.pk)


@pytest.mark.django_db
def test_dry_run_has_no_database_or_s3_writes(tmp_path, settings):
    """Dry-run ограничивается чтением пакета и БД."""
    package, _, source_key, content = _prepare_audio_package(tmp_path)
    settings.USE_S3_MEDIA = True
    client = FakeS3Client(source_key=source_key, content=content)

    with patch.object(
        TrackUploadStorageService,
        '_get_s3_client',
        return_value=client,
    ):
        result = CatalogAudioImporter(package, dry_run=True).run()

    assert result.would_start == 1
    assert CatalogMigrationAudioState.objects.count() == 0
    assert TrackUpload.objects.count() == 0
    assert client.copies == []


@pytest.mark.django_db
def test_v2_uses_exact_namespace_and_source_key_and_skips_missing(
    tmp_path,
    settings,
):
    """v2 выбирает AVAILABLE asset, а явные MISSING оставляет без аудио."""
    package = v2_package(tmp_path)
    bundle = bundle_root(package)
    content = b'canonical source audio'
    digest = hashlib.sha256(content).hexdigest()
    tracks_path = bundle / 'data/tracks.json'
    tracks = _load(tracks_path)
    selected_track = tracks[0]
    selected_track.update({
        'audio_asset_id': 'audio-v2-test',
        'audio_status': 'AVAILABLE',
        'original_filename': 'source.wav',
    })
    _write_json(tracks_path, tracks)
    asset = {
        'asset_id': 'audio-v2-test',
        'bundle_path': 'media/audio/originals/audio-v2-test.wav',
        'entity_id': selected_track['entity_id'],
        'entity_type': 'track',
        'format': 'wav',
        'original_filename': 'source.wav',
        'role': 'audio_original',
        'selection_status': 'SELECTED',
        'sha256': digest,
        'size': len(content),
        'state': 'EXPECTED_CANONICAL_ORIGINAL',
    }
    _write_json(
        bundle / 'media/manifests/audio.json',
        {'assets': [asset]},
    )
    bundle_path = bundle / 'bundle.json'
    bundle_document = _load(bundle_path)
    bundle_document['expected_counts']['expected_audio_assets'] = 1
    _write_json(bundle_path, bundle_document)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    codes = _load(package / 'artist_codes.json')
    config['artist_code_whitelist'] = [codes['artists'][0]['code']]
    _write_json(config_path, config)
    settings.USE_S3_MEDIA = True
    CatalogProfileImporter(package).run()
    CatalogReleaseImporter(package).run()
    CatalogTrackImporter(package).run()

    with patch.object(
        TrackUploadStorageService,
        '_get_s3_client',
        side_effect=AssertionError('dry-run must not access S3'),
    ) as get_s3_client:
        importer = CatalogAudioImporter(package, dry_run=True)
        result = importer.run()

    candidates = importer._load_candidates(config)
    candidate = candidates[selected_track['entity_id']]
    assert result.selected == 1
    assert result.would_start == 1
    assert candidate.mapping.bundle_version == mapping_version(package)
    assert candidate.source_key == (
        'migration-v2/zvuchno-migration-bundle-v2/'
        'media/audio/originals/audio-v2-test.wav'
    )
    assert candidate.staging_key.startswith(
        'staging/catalog-migration/v2/',
    )
    assert set(candidates) == {selected_track['entity_id']}
    assert CatalogMigrationAudioState.objects.count() == 0
    assert TrackUpload.objects.count() == 0
    get_s3_client.assert_not_called()


@pytest.mark.django_db
def test_missing_s3_checksum_uses_real_sha256_not_etag(tmp_path, settings):
    """Без S3 checksum считается содержимое, а ETag игнорируется."""
    package, _, source_key, content = _prepare_audio_package(tmp_path)
    settings.USE_S3_MEDIA = True
    client = FakeS3Client(
        source_key=source_key,
        content=b'x' * len(content),
        checksum=False,
    )

    with (
        patch.object(
            TrackUploadStorageService,
            '_get_s3_client',
            return_value=client,
        ),
        patch(
            'catalog_migration.services.catalog_audio_import.'
            'TrackGeneratedAudioScheduler.enqueue',
        ),
        pytest.raises(CatalogAudioImportError, match='failed=1'),
    ):
        CatalogAudioImporter(package).run()

    assert client.copies == []
    assert CatalogMigrationAudioState.objects.get().status == (
        CatalogMigrationAudioState.Status.FAILED
    )


@pytest.mark.django_db
def test_enqueue_failure_is_recorded_not_reported_ready(tmp_path, settings):
    """Ошибка broker сохраняется как FAILED, а не READY."""
    package, _, source_key, content = _prepare_audio_package(tmp_path)
    settings.USE_S3_MEDIA = True
    client = FakeS3Client(source_key=source_key, content=content)

    with (
        patch.object(
            TrackUploadStorageService,
            '_get_s3_client',
            return_value=client,
        ),
        patch(
            'catalog_migration.services.catalog_audio_import.'
            'TrackGeneratedAudioScheduler.enqueue',
            side_effect=ConnectionError('broker unavailable'),
        ),
        pytest.raises(CatalogAudioImportError, match='Celery'),
    ):
        CatalogAudioImporter(package).run()

    state = CatalogMigrationAudioState.objects.get()
    assert state.status == CatalogMigrationAudioState.Status.FAILED
    assert state.error == 'ConnectionError'


@pytest.mark.django_db
def test_processing_attempt_is_not_enqueued_twice(tmp_path, settings):
    """Недавняя очередь не получает повторную задачу."""
    package, track, source_key, content = _prepare_audio_package(tmp_path)
    settings.USE_S3_MEDIA = True
    client = FakeS3Client(source_key=source_key, content=content)

    with (
        patch.object(
            TrackUploadStorageService,
            '_get_s3_client',
            return_value=client,
        ),
        patch(
            'catalog_migration.services.catalog_audio_import.'
            'TrackGeneratedAudioScheduler.enqueue',
        ) as enqueue,
    ):
        CatalogAudioImporter(package).run()
        second = CatalogAudioImporter(package).run()

    assert second.processing == 1
    enqueue.assert_called_once_with(track.pk)
    assert len(client.copies) == 2


@pytest.mark.django_db
def test_ready_track_is_skipped_and_generated_keys_are_recorded(
    tmp_path,
    settings,
):
    """Готовый Track пропускается, а generated keys фиксируются."""
    package, track, source_key, content = _prepare_audio_package(tmp_path)
    settings.USE_S3_MEDIA = True
    client = FakeS3Client(source_key=source_key, content=content)
    with (
        patch.object(
            TrackUploadStorageService,
            '_get_s3_client',
            return_value=client,
        ),
        patch(
            'catalog_migration.services.catalog_audio_import.'
            'TrackGeneratedAudioScheduler.enqueue',
        ),
    ):
        CatalogAudioImporter(package).run()

    track.refresh_from_db()
    track.duration = 120
    track.save(update_fields=('duration',))
    TrackGeneratedAudio.objects.create(
        track=track,
        preview_file='preview/file.mp3',
        preview_status=TrackGeneratedAudio.ProcessingStatus.READY,
        stream_file='stream/file.mp3',
        stream_status=TrackGeneratedAudio.ProcessingStatus.READY,
    )
    with patch(
        'catalog_migration.services.catalog_audio_import.TrackGeneratedAudioScheduler.enqueue',
    ) as enqueue:
        result = CatalogAudioImporter(package).run()

    state = CatalogMigrationAudioState.objects.get()
    assert result.ready == 1
    assert state.status == CatalogMigrationAudioState.Status.READY
    assert state.preview_key == 'preview/file.mp3'
    assert state.stream_key == 'stream/file.mp3'
    enqueue.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_final_copy_db_failure_reuses_same_keys_on_explicit_retry(
    tmp_path,
    settings,
    monkeypatch,
):
    """Повтор после DB-сбоя использует те же staging/final keys."""
    package, _, source_key, content = _prepare_audio_package(tmp_path)
    settings.USE_S3_MEDIA = True
    client = FakeS3Client(source_key=source_key, content=content)
    original_save = TrackUpload.save
    should_fail = True

    def fail_first_completion(self, *args, **kwargs) -> Any:
        nonlocal should_fail
        if self.status == TrackUpload.Status.COMPLETED and should_fail:
            should_fail = False
            raise IntegrityError('simulated completion failure')
        return original_save(self, *args, **kwargs)

    monkeypatch.setattr(TrackUpload, 'save', fail_first_completion)
    with (
        patch.object(
            TrackUploadStorageService,
            '_get_s3_client',
            return_value=client,
        ),
        patch(
            'catalog_migration.services.catalog_audio_import.'
            'TrackGeneratedAudioScheduler.enqueue',
        ),
        pytest.raises(CatalogAudioImportError, match='failed=1'),
    ):
        CatalogAudioImporter(package).run()

    state = CatalogMigrationAudioState.objects.get()
    staging_key = state.staging_key
    original_key = state.original_key

    with (
        patch.object(
            TrackUploadStorageService,
            '_get_s3_client',
            return_value=client,
        ),
        patch(
            'catalog_migration.services.catalog_audio_import.'
            'TrackGeneratedAudioScheduler.enqueue',
        ),
    ):
        CatalogAudioImporter(package, retry_errors=True).run()

    state.refresh_from_db()
    assert state.staging_key == staging_key
    assert state.original_key == original_key
    target_keys = [item['Key'] for item in client.copies]
    assert (
        target_keys.count(
            TrackUploadStorageService._get_bucket_key(original_key),
        )
        == 2
    )


@pytest.mark.django_db
def test_track_filter_rejects_entity_outside_whitelist(tmp_path):
    """Точечный фильтр не обходит whitelist."""
    package, _, _, _ = _prepare_audio_package(tmp_path)
    with pytest.raises(CatalogAudioImportError, match='не входит.*track-01'):
        CatalogAudioImporter(
            package,
            dry_run=True,
            track_entity_id='track-01',
        ).run()


@pytest.mark.django_db
def test_mapping_conflict_blocks_s3_before_copy(tmp_path):
    """Конфликт TRACK/RELEASE mapping блокирует обращение к S3."""
    package, track, _, _ = _prepare_audio_package(tmp_path)
    other_album = _create_album_mapping(package, 1)
    track.album = other_album
    track.save(update_fields=('album',))

    with pytest.raises(CatalogAudioImportError, match='RELEASE mapping'):
        CatalogAudioImporter(package, dry_run=True).run()

    track.refresh_from_db()
    assert not track.audio_file


@pytest.mark.django_db
def test_existing_audio_without_migration_state_is_conflict(tmp_path):
    """Импорт не перезаписывает оригинал, добавленный человеком."""
    package, track, _, _ = _prepare_audio_package(tmp_path)
    track.audio_file.name = 'albums/manual/original.wav'
    track.save(update_fields=('audio_file',))

    with pytest.raises(CatalogAudioImportError, match='конфликтует'):
        CatalogAudioImporter(package, dry_run=True).run()

    assert CatalogMigrationAudioState.objects.count() == 0
    assert TrackUpload.objects.count() == 0


@pytest.mark.django_db
def test_stale_queued_work_is_not_enqueued_again_by_retry(
    tmp_path,
    settings,
):
    """Ожидающая в broker задача не дублируется по локальному таймауту."""
    package, track, source_key, content = _prepare_audio_package(tmp_path)
    settings.USE_S3_MEDIA = True
    client = FakeS3Client(source_key=source_key, content=content)
    with (
        patch.object(
            TrackUploadStorageService,
            '_get_s3_client',
            return_value=client,
        ),
        patch(
            'catalog_migration.services.catalog_audio_import.'
            'TrackGeneratedAudioScheduler.enqueue',
        ),
    ):
        CatalogAudioImporter(package).run()

    stale_at = timezone.now() - timedelta(hours=2)
    TrackGeneratedAudio.objects.create(
        track=track,
        preview_status=TrackGeneratedAudio.ProcessingStatus.BUILDING,
        preview_started_at=stale_at,
        stream_status=TrackGeneratedAudio.ProcessingStatus.BUILDING,
        stream_started_at=stale_at,
    )

    regular_plan = CatalogAudioImporter(package, dry_run=True).run()
    assert regular_plan.would_start == 0
    assert regular_plan.processing == 1

    retry_plan = CatalogAudioImporter(
        package,
        dry_run=True,
        retry_errors=True,
    ).run()
    assert retry_plan.would_start == 0
    assert retry_plan.processing == 1

    with patch(
        'catalog_migration.services.catalog_audio_import.'
        'TrackGeneratedAudioScheduler.enqueue',
    ) as enqueue:
        result = CatalogAudioImporter(package, retry_errors=True).run()

    assert result.queued == 0
    assert result.processing == 1
    enqueue.assert_not_called()


@pytest.mark.django_db
def test_failed_retry_dry_run_matches_real_plan_without_recopies(
    tmp_path,
    settings,
):
    """FAILED retry переиспользует upload/original и исключает параллель."""
    package, track, source_key, content = _prepare_audio_package(tmp_path)
    settings.USE_S3_MEDIA = True
    client = FakeS3Client(source_key=source_key, content=content)
    with (
        patch.object(
            TrackUploadStorageService,
            '_get_s3_client',
            return_value=client,
        ),
        patch(
            'catalog_migration.services.catalog_audio_import.'
            'TrackGeneratedAudioScheduler.enqueue',
        ),
    ):
        CatalogAudioImporter(package).run()

    TrackGeneratedAudio.objects.create(
        track=track,
        preview_status=TrackGeneratedAudio.ProcessingStatus.FAILED,
        preview_error='old failure',
        stream_status=TrackGeneratedAudio.ProcessingStatus.FAILED,
        stream_error='old failure',
    )
    original_upload_id = CatalogMigrationAudioState.objects.get().upload_id
    original_copy_count = len(client.copies)

    dry_run = CatalogAudioImporter(
        package,
        dry_run=True,
        retry_errors=True,
    ).run()
    assert dry_run.would_start == 1

    with (
        patch.object(
            TrackUploadStorageService,
            '_get_s3_client',
            return_value=client,
        ),
        patch(
            'catalog_migration.services.catalog_audio_import.'
            'TrackGeneratedAudioScheduler.enqueue',
        ) as enqueue,
    ):
        actual = CatalogAudioImporter(package, retry_errors=True).run()
        repeated = CatalogAudioImporter(package, retry_errors=True).run()

    state = CatalogMigrationAudioState.objects.get()
    generated = TrackGeneratedAudio.objects.get(track=track)
    assert actual.queued == dry_run.would_start == 1
    assert repeated.processing == 1
    assert repeated.queued == 0
    assert state.upload_id == original_upload_id
    assert TrackUpload.objects.count() == 1
    assert len(client.copies) == original_copy_count
    assert generated.preview_status == (
        TrackGeneratedAudio.ProcessingStatus.PENDING
    )
    assert generated.stream_status == (
        TrackGeneratedAudio.ProcessingStatus.PENDING
    )
    enqueue.assert_called_once_with(track.pk)


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_failed_retries_enqueue_only_once(
    tmp_path,
    settings,
):
    """Два устаревших плана retry повторно проверяются под row lock."""
    if connection.vendor != 'postgresql':
        pytest.skip('Конкурентная проверка требует PostgreSQL')

    package, track, source_key, content = _prepare_audio_package(tmp_path)
    settings.USE_S3_MEDIA = True
    client = FakeS3Client(source_key=source_key, content=content)
    with (
        patch.object(
            TrackUploadStorageService,
            '_get_s3_client',
            return_value=client,
        ),
        patch(
            'catalog_migration.services.catalog_audio_import.'
            'TrackGeneratedAudioScheduler.enqueue',
        ),
    ):
        CatalogAudioImporter(package).run()

    TrackGeneratedAudio.objects.create(
        track=track,
        preview_status=TrackGeneratedAudio.ProcessingStatus.FAILED,
        stream_status=TrackGeneratedAudio.ProcessingStatus.FAILED,
    )
    upload_id = CatalogMigrationAudioState.objects.get().upload_id
    copy_count = len(client.copies)
    classified = Barrier(2)
    first_enqueued = Event()

    class CoordinatedImporter(CatalogAudioImporter):
        """Фиксирует худший порядок двух устаревших классификаций."""

        def __init__(self, *args, delayed_claim=False, **kwargs):
            super().__init__(*args, **kwargs)
            self.delayed_claim = delayed_claim
            self.classification_synchronised = False

        def _classify(self, candidate: AudioCandidate) -> str:
            status = super()._classify(candidate)
            if status == 'retry' and not self.classification_synchronised:
                self.classification_synchronised = True
                classified.wait(timeout=5)
            return status

        def _claim_state(
            self,
            candidate: AudioCandidate,
            *,
            retry: bool,
        ) -> CatalogMigrationAudioState | None:
            if self.delayed_claim:
                assert first_enqueued.wait(timeout=5)
            return super()._claim_state(candidate, retry=retry)

    importers = (
        CoordinatedImporter(package, retry_errors=True),
        CoordinatedImporter(
            package,
            retry_errors=True,
            delayed_claim=True,
        ),
    )

    def run_import(
        importer: CatalogAudioImporter,
    ) -> CatalogAudioImportResult:
        close_old_connections()
        try:
            return importer.run()
        finally:
            close_old_connections()

    def enqueue_once(track_id: int) -> int:
        first_enqueued.set()
        return track_id

    with (
        patch.object(
            TrackUploadStorageService,
            '_get_s3_client',
            return_value=client,
        ),
        patch(
            'catalog_migration.services.catalog_audio_import.'
            'TrackGeneratedAudioScheduler.enqueue',
            side_effect=enqueue_once,
        ) as enqueue,
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        results = list(executor.map(run_import, importers))

    assert sum(result.queued for result in results) == 1
    assert enqueue.call_count == 1
    assert CatalogMigrationAudioState.objects.get().upload_id == upload_id
    assert TrackUpload.objects.count() == 1
    assert len(client.copies) == copy_count
