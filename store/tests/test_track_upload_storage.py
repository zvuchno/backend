"""Тесты завершения загрузки оригинальных файлов треков."""

from unittest.mock import patch

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile

from store.models import Track, TrackUpload
from store.services.track_upload import (
    TrackUploadService,
    TrackUploadStorageError,
    TrackUploadStorageService,
)
from store.tests.factories import AlbumFactory


@pytest.mark.django_db
class TestTrackUploadStorageService:
    """Тесты переноса staging-файлов в постоянное хранилище."""

    def test_completes_local_upload_and_removes_staging_file(
        self,
        settings,
        tmp_path,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Завершает local upload, назначает оригинал и удаляет staging."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Track._meta.get_field('audio_file')

        monkeypatch.setattr(
            audio_file_field,
            'storage',
            storage,
        )

        album = AlbumFactory()
        file_content = b'test audio content'

        track, upload = TrackUploadService.create_pending_track(
            album=album,
            filename='01 Intro.flac',
            size=len(file_content),
            content_type='audio/flac',
        )

        uploaded_file = SimpleUploadedFile(
            name='01 Intro.flac',
            content=file_content,
            content_type='audio/flac',
        )

        received_upload = TrackUploadService.receive_local_file(
            upload=upload,
            uploaded_file=uploaded_file,
        )

        assert received_upload.status == TrackUpload.Status.UPLOADED
        assert storage.exists(upload.staging_key)

        with patch(
            'store.services.track_upload.upload_storage.'
            'TrackGeneratedAudioScheduler.schedule',
            return_value=True,
        ) as mocked_schedule:
            with django_capture_on_commit_callbacks(execute=True):
                completed_upload = TrackUploadStorageService.complete(
                    upload=received_upload,
                )

        track.refresh_from_db()
        completed_upload.refresh_from_db()

        assert completed_upload.status == TrackUpload.Status.COMPLETED
        assert completed_upload.uploaded_size == len(file_content)
        assert completed_upload.completed_at is not None
        assert completed_upload.error == ''

        assert track.audio_file.name
        assert track.audio_file.name.startswith(
            f'albums/{album.pk}/tracks/original/',
        )
        assert track.audio_file.name.endswith('.flac')

        assert storage.exists(track.audio_file.name)
        assert not storage.exists(upload.staging_key)

        with storage.open(track.audio_file.name, 'rb') as audio_file:
            assert audio_file.read() == file_content

        mocked_schedule.assert_called_once_with(track)

    def test_raises_error_when_local_staging_file_is_missing(
        self,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """Не завершает загрузку без файла во временном хранилище."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Track._meta.get_field('audio_file')

        monkeypatch.setattr(
            audio_file_field,
            'storage',
            storage,
        )

        album = AlbumFactory()

        _, upload = TrackUploadService.create_pending_track(
            album=album,
            filename='missing.flac',
            size=10,
            content_type='audio/flac',
        )

        with pytest.raises(
            TrackUploadStorageError,
            match='Временный файл загрузки не найден',
        ):
            TrackUploadStorageService.complete(upload=upload)

        upload.refresh_from_db()

        assert upload.status == TrackUpload.Status.INITIATED
        assert upload.completed_at is None
