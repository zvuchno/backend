import zipfile
from unittest.mock import patch

import pytest

from store.models import AlbumArchive
from store.services.album_archive import AlbumArchiveService
from store.tasks import build_album_archive
from store.tests.factories import (
    AlbumFactory,
    TrackFactory,
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

    TrackFactory(
        album=album,
        name='Первый / трек',
        position=1,
        audio_file=make_audio_file(
            name='first.mp3',
            content=b'first-audio',
        ),
    )

    TrackFactory(
        album=album,
        name='Второй трек',
        position=2,
        audio_file=make_audio_file(
            name='second.flac',
            content=b'second-audio',
        ),
    )

    return album


def prepare_archive(album):
    """Создает ожидающую запись архива."""
    tracks = list(
        album.tracks.order_by('position', 'id'),
    )

    expected_hash = AlbumArchiveService.calculate_content_hash(
        album=album,
        tracks=tracks,
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
    """Отсутствующий исходный файл переводит архив в FAILED."""
    album = album_with_tracks
    archive, expected_hash = prepare_archive(album)

    track = album.tracks.order_by('position', 'id').first()
    track.audio_file.storage.delete(track.audio_file.name)

    with pytest.raises(FileNotFoundError):
        AlbumArchiveService.build(
            album_id=album.pk,
            expected_hash=expected_hash,
        )

    archive.refresh_from_db()

    assert archive.status == AlbumArchive.Status.FAILED
    assert archive.error_message
    assert archive.pending_hash == expected_hash
    assert not archive.file


def test_content_hash_changes_after_track_update(
    album_with_tracks,
):
    """Изменение трека меняет хеш содержимого архива."""
    album = album_with_tracks

    tracks = list(
        album.tracks.order_by('position', 'id'),
    )

    old_hash = AlbumArchiveService.calculate_content_hash(
        album=album,
        tracks=tracks,
    )

    track = tracks[0]
    track.name = 'Новое название'
    track.save(update_fields=('name',))

    new_hash = AlbumArchiveService.calculate_content_hash(
        album=album,
        tracks=list(
            album.tracks.order_by('position', 'id'),
        ),
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
