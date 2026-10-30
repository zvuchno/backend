import zipfile
from unittest.mock import patch

import pytest

from store.models import AlbumArchive
from store.services.album_archive import (
    AlbumArchiveScheduler,
    AlbumArchiveService,
)
from store.tasks.album_archive import build_album_archive
from store.tests.factories import (
    AlbumFactory,
    ReleaseTrackFactory,
    make_audio_file,
    make_cover_file,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def local_media(settings, tmp_path):
    """Изолирует медиафайлы каждого теста."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def album_with_tracks(local_media):
    """Создает альбом с обложкой и двумя треками."""
    album = AlbumFactory(
        cover_image=make_cover_file(
            name='cover.jpg',
            content=b'cover-content',
        ),
    )

    ReleaseTrackFactory(
        release=album,
        position=1,
        recording__name='Первый / трек',
        recording__audio_file=make_audio_file(
            name='first.mp3',
            content=b'first-audio',
        ),
    )

    ReleaseTrackFactory(
        release=album,
        position=2,
        recording__name='Второй трек',
        recording__audio_file=make_audio_file(
            name='second.flac',
            content=b'second-audio',
        ),
    )

    return album


def prepare_archive(album):
    """Создает ожидающую запись архива."""
    tracks = list(
        album.tracks.filter(is_active=True).order_by('position', 'id'),
    )
    bonuses = list(
        album.bonuses.filter(is_active=True).order_by('name', 'id'),
    )

    expected_hash = AlbumArchiveService.calculate_content_hash(
        album=album,
        tracks=tracks,
        bonuses=bonuses,
    )

    archive = AlbumArchive.objects.create(
        album=album,
        status=AlbumArchive.Status.PENDING,
        pending_hash=expected_hash,
    )

    return archive, expected_hash


def test_build_creates_ready_zip_with_cover_and_tracks(
    album_with_tracks,
):
    """Сервис создает готовый ZIP с исходными файлами."""
    album = album_with_tracks
    archive, expected_hash = prepare_archive(album)

    result = AlbumArchiveService.build(
        album_id=album.pk,
        expected_hash=expected_hash,
    )

    result.refresh_from_db()

    assert result.pk == archive.pk
    assert result.status == AlbumArchive.Status.READY
    assert result.content_hash == expected_hash
    assert result.pending_hash == ''
    assert result.error_message == ''
    assert result.file.name

    with result.file.open('rb') as archive_file:
        with zipfile.ZipFile(archive_file) as zip_file:
            assert zip_file.namelist() == [
                'cover.jpg',
                '01 - Первый - трек.mp3',
                '02 - Второй трек.flac',
            ]

            assert zip_file.read('cover.jpg') == b'cover-content'
            assert zip_file.read('01 - Первый - трек.mp3') == b'first-audio'
            assert zip_file.read('02 - Второй трек.flac') == b'second-audio'

            for item in zip_file.infolist():
                assert item.compress_type == zipfile.ZIP_STORED


def test_build_skips_outdated_task(album_with_tracks):
    """Старая задача не изменяет запись архива."""
    album = album_with_tracks
    archive, current_hash = prepare_archive(album)

    result = AlbumArchiveService.build(
        album_id=album.pk,
        expected_hash='outdated-hash',
    )

    archive.refresh_from_db()

    assert result.pk == archive.pk
    assert archive.status == AlbumArchive.Status.PENDING
    assert archive.pending_hash == current_hash
    assert not archive.file


def test_build_marks_archive_failed_when_source_file_is_missing(
    album_with_tracks,
):
    """Отсутствующий исходник помечает архив ошибочным без исключения."""
    album = album_with_tracks
    archive, expected_hash = prepare_archive(album)

    track = album.tracks.order_by('position', 'id').first()
    track.recording.audio_file.storage.delete(
        track.recording.audio_file.name,
    )

    result = AlbumArchiveService.build(
        album_id=album.pk,
        expected_hash=expected_hash,
    )

    archive.refresh_from_db()

    assert result.pk == archive.pk
    assert archive.status == AlbumArchive.Status.FAILED
    assert 'отсутствует в хранилище' in archive.error_message


def test_content_hash_changes_after_track_update(
    album_with_tracks,
):
    """Изменение трека меняет хеш содержимого архива."""
    album = album_with_tracks

    tracks = list(
        album.tracks.filter(is_active=True).order_by('position', 'id'),
    )
    bonuses = list(
        album.bonuses.filter(is_active=True).order_by('name', 'id'),
    )

    old_hash = AlbumArchiveService.calculate_content_hash(
        album=album,
        tracks=tracks,
        bonuses=bonuses,
    )

    track = tracks[0]
    track.recording.name = 'Новое название'
    track.recording.save(update_fields=('name',))

    new_hash = AlbumArchiveService.calculate_content_hash(
        album=album,
        tracks=list(
            album.tracks.order_by('position', 'id'),
        ),
        bonuses=bonuses,
    )

    assert new_hash != old_hash


def test_content_hash_ignores_recording_file_hash(album_with_tracks):
    """Асинхронное появление SHA-256 не меняет fingerprint архива."""
    album = album_with_tracks
    tracks = list(
        album.tracks.select_related('recording').order_by('position', 'id'),
    )
    bonuses = list(album.bonuses.order_by('name', 'id'))

    old_hash = AlbumArchiveService.calculate_content_hash(
        album=album,
        tracks=tracks,
        bonuses=bonuses,
    )

    recording = tracks[0].recording
    original_audio_name = recording.audio_file.name
    recording.file_hash = 'calculated-later'
    recording.save(update_fields=('file_hash',))

    refreshed_tracks = list(
        album.tracks.select_related('recording').order_by('position', 'id'),
    )
    new_hash = AlbumArchiveService.calculate_content_hash(
        album=album,
        tracks=refreshed_tracks,
        bonuses=bonuses,
    )

    assert recording.audio_file.name == original_audio_name
    assert new_hash == old_hash


def test_content_hash_changes_with_recording_audio_storage_key(
    album_with_tracks,
):
    """Замена storage key original меняет fingerprint архива."""
    album = album_with_tracks
    tracks = list(
        album.tracks.select_related('recording').order_by('position', 'id'),
    )
    bonuses = list(album.bonuses.order_by('name', 'id'))
    old_hash = AlbumArchiveService.calculate_content_hash(
        album=album,
        tracks=tracks,
        bonuses=bonuses,
    )

    recording = tracks[0].recording
    recording.audio_file.name = 'recordings/original/replacement.mp3'
    recording.save(update_fields=('audio_file',))

    new_hash = AlbumArchiveService.calculate_content_hash(
        album=album,
        tracks=list(
            album.tracks.select_related('recording').order_by(
                'position',
                'id',
            ),
        ),
        bonuses=bonuses,
    )

    assert new_hash != old_hash


def test_task_skips_when_archive_does_not_exist():
    """Удаленная запись архива не запускает сервис."""
    album = AlbumFactory()

    with patch(
        'store.tasks.album_archive.AlbumArchiveService.build',
    ) as build_mock:
        build_album_archive(
            album_id=album.pk,
            expected_hash='expected-hash',
        )

    build_mock.assert_not_called()


def test_task_skips_outdated_pending_hash():
    """Старая задача не запускает сборку."""
    album = AlbumFactory()

    AlbumArchive.objects.create(
        album=album,
        status=AlbumArchive.Status.PENDING,
        pending_hash='current-hash',
    )

    with patch(
        'store.tasks.album_archive.AlbumArchiveService.build',
    ) as build_mock:
        build_album_archive(
            album_id=album.pk,
            expected_hash='outdated-hash',
        )

    build_mock.assert_not_called()


def test_task_calls_service_for_current_pending_hash():
    """Актуальная задача вызывает сервис сборки."""
    album = AlbumFactory()

    AlbumArchive.objects.create(
        album=album,
        status=AlbumArchive.Status.PENDING,
        pending_hash='current-hash',
    )

    with patch(
        'store.tasks.album_archive.AlbumArchiveService.build',
    ) as build_mock:
        build_album_archive(
            album_id=album.pk,
            expected_hash='current-hash',
        )

    build_mock.assert_called_once_with(
        album_id=album.pk,
        expected_hash='current-hash',
    )


def test_build_excludes_inactive_tracks(
    album_with_tracks,
):
    """Неактивный трек не попадает в актуальный ZIP-архив."""
    album = album_with_tracks
    inactive_track = album.tracks.get(position=2)

    inactive_track.is_active = False
    inactive_track.save(update_fields=('is_active',))

    archive, expected_hash = prepare_archive(album)

    result = AlbumArchiveService.build(
        album_id=album.pk,
        expected_hash=expected_hash,
    )

    result.refresh_from_db()

    assert result.status == AlbumArchive.Status.READY

    with result.file.open('rb') as archive_file:
        with zipfile.ZipFile(archive_file) as zip_file:
            assert zip_file.namelist() == [
                'cover.jpg',
                '01 - Первый - трек.mp3',
            ]

            assert zip_file.read('01 - Первый - трек.mp3') == b'first-audio'


@pytest.mark.parametrize(
    ('status', 'pending_hash'),
    (
        (AlbumArchive.Status.READY, 'failed-hash'),
        (AlbumArchive.Status.BUILDING, 'failed-hash'),
        (AlbumArchive.Status.PENDING, 'newer-hash'),
    ),
)
@patch(
    'store.tasks.album_archive.build_album_archive.apply_async',
    side_effect=RuntimeError('Broker unavailable'),
)
def test_enqueue_failure_does_not_overwrite_newer_archive_state(
    _mocked_task,
    status,
    pending_hash,
):
    """Ошибка старого enqueue не меняет актуальное состояние архива."""
    album = AlbumFactory()
    archive = AlbumArchive.objects.create(
        album=album,
        status=status,
        pending_hash=pending_hash,
        error_message='current state',
    )

    AlbumArchiveScheduler._enqueue_safely(
        album_id=album.pk,
        content_hash='failed-hash',
    )

    archive.refresh_from_db()

    assert archive.status == status
    assert archive.pending_hash == pending_hash
    assert archive.error_message == 'current state'


@patch(
    'store.tasks.album_archive.build_album_archive.apply_async',
)
def test_scheduler_rebuilds_archive_after_track_deactivation(
    _mocked_task,
    album_with_tracks,
):
    """Деактивация трека меняет состав актуального архива."""
    album = album_with_tracks

    active_tracks = list(
        album.tracks.filter(is_active=True).order_by('position', 'id'),
    )
    bonuses = list(
        album.bonuses.filter(is_active=True).order_by('name', 'id'),
    )

    old_hash = AlbumArchiveService.calculate_content_hash(
        album=album,
        tracks=active_tracks,
        bonuses=bonuses,
    )

    AlbumArchive.objects.create(
        album=album,
        status=AlbumArchive.Status.READY,
        content_hash=old_hash,
    )

    track = album.tracks.get(position=2)
    track.is_active = False
    track.save(update_fields=('is_active',))

    scheduled = AlbumArchiveScheduler.schedule(album)

    archive = AlbumArchive.objects.get(album=album)

    expected_hash = AlbumArchiveService.calculate_content_hash(
        album=album,
        tracks=list(
            album.tracks.filter(is_active=True).order_by('position', 'id'),
        ),
        bonuses=bonuses,
    )

    assert scheduled is True
    assert archive.status == AlbumArchive.Status.PENDING
    assert archive.pending_hash == expected_hash
    assert archive.pending_hash != old_hash


def test_scheduler_invalidates_archive_when_last_track_deactivated(
    album_with_tracks,
):
    """Архив недоступен, если в релизе не осталось активных треков."""
    album = album_with_tracks

    archive = AlbumArchive.objects.create(
        album=album,
        status=AlbumArchive.Status.READY,
        content_hash='old-hash',
    )
    archive.file.name = 'test/archives/old.zip'
    archive.save(update_fields=('file',))

    for track in album.tracks.all():
        track.is_active = False
        track.save(update_fields=('is_active',))

    scheduled = AlbumArchiveScheduler.schedule(album)

    archive.refresh_from_db()

    assert scheduled is False
    assert archive.status == AlbumArchive.Status.PENDING
    assert archive.content_hash == ''
    assert archive.pending_hash == ''
    assert not archive.file
