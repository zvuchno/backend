"""Тесты очистки заброшенных загрузок оригинальных файлов треков."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from store.models import Product, Recording, ReleaseTrack, TrackUpload
from store.services import ProductService
from store.services.track_upload import (
    TrackUploadCleanupService,
    TrackUploadService,
)
from store.tests.factories import ReleaseTrackFactory


@pytest.mark.django_db
class TestTrackUploadCleanupService:
    """Тесты уборки технических треков и staging-файлов."""

    def test_deletes_abandoned_upload_and_recording(
        self,
        artist_user,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """Удаляет staging, независимую Recording и upload."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Recording._meta.get_field('audio_file')

        monkeypatch.setattr(
            audio_file_field,
            'storage',
            storage,
        )

        file_content = b'test audio content'

        recording, upload = TrackUploadService.create_recording_upload(
            owner=artist_user.artist_profile,
            created_by=artist_user,
            filename='abandoned.flac',
            size=len(file_content),
            content_type='audio/flac',
        )

        TrackUploadService.receive_local_file(
            upload=upload,
            uploaded_file=SimpleUploadedFile(
                name='abandoned.flac',
                content=file_content,
                content_type='audio/flac',
            ),
        )

        upload.refresh_from_db()

        TrackUpload.objects.filter(pk=upload.pk).update(
            expires_at=timezone.now() - timedelta(days=2),
        )

        assert storage.exists(upload.staging_key)
        assert not recording.release_tracks.exists()

        result = TrackUploadCleanupService.cleanup_expired()

        assert result == {
            'deleted': 1,
            'skipped': 0,
            'storage_errors': 0,
        }
        assert not storage.exists(upload.staging_key)
        assert not Recording.objects.filter(pk=recording.pk).exists()
        assert not TrackUpload.objects.filter(pk=upload.pk).exists()

    def test_keeps_recent_pending_upload(
        self,
        artist_user,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """Не удаляет запись до истечения срока очистки."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Recording._meta.get_field('audio_file')

        monkeypatch.setattr(
            audio_file_field,
            'storage',
            storage,
        )

        recording, upload = TrackUploadService.create_recording_upload(
            owner=artist_user.artist_profile,
            created_by=artist_user,
            filename='recent.flac',
            size=10,
            content_type='audio/flac',
        )

        result = TrackUploadCleanupService.cleanup_expired()

        assert result == {
            'deleted': 0,
            'skipped': 0,
            'storage_errors': 0,
        }
        assert Recording.objects.filter(pk=recording.pk).exists()
        assert TrackUpload.objects.filter(pk=upload.pk).exists()

    def test_keeps_upload_when_staging_cleanup_fails(
        self,
        artist_user,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """Не удаляет запись, если staging-файл удалить не удалось."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Recording._meta.get_field('audio_file')

        monkeypatch.setattr(
            audio_file_field,
            'storage',
            storage,
        )

        recording, upload = TrackUploadService.create_recording_upload(
            owner=artist_user.artist_profile,
            created_by=artist_user,
            filename='failed-cleanup.flac',
            size=10,
            content_type='audio/flac',
        )

        TrackUpload.objects.filter(pk=upload.pk).update(
            expires_at=timezone.now() - timedelta(days=2),
        )

        with patch(
            'store.services.track_upload.clean_up.'
            'TrackUploadStorageService.delete_staging',
            side_effect=RuntimeError('Storage unavailable'),
        ):
            result = TrackUploadCleanupService.cleanup_expired()

        assert result == {
            'deleted': 0,
            'skipped': 0,
            'storage_errors': 1,
        }
        assert Recording.objects.filter(pk=recording.pk).exists()
        assert TrackUpload.objects.filter(pk=upload.pk).exists()

    def test_replacement_cleanup_keeps_recording_release_track_and_product(
        self,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """Для REPLACE удаляет только staging и TrackUpload."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Recording._meta.get_field('audio_file')
        monkeypatch.setattr(audio_file_field, 'storage', storage)

        release_track = ReleaseTrackFactory()
        recording = release_track.recording
        ProductService.ensure_commerce(
            release_track,
            validated_data={
                'price': 0,
                'allow_overpay': False,
                'variants': [],
            },
        )
        original_audio_name = recording.audio_file.name
        staging_content = b'replacement audio'
        upload = TrackUploadService.create_replacement_upload(
            recording=recording,
            filename='replacement.flac',
            size=len(staging_content),
            content_type='audio/flac',
        )
        TrackUploadService.receive_local_file(
            upload=upload,
            uploaded_file=SimpleUploadedFile(
                name='replacement.flac',
                content=staging_content,
                content_type='audio/flac',
            ),
        )
        TrackUpload.objects.filter(pk=upload.pk).update(
            expires_at=timezone.now() - timedelta(days=2),
        )

        assert storage.exists(upload.staging_key)

        result = TrackUploadCleanupService.cleanup_expired()

        assert result == {
            'deleted': 1,
            'skipped': 0,
            'storage_errors': 0,
        }
        assert not storage.exists(upload.staging_key)
        assert not TrackUpload.objects.filter(pk=upload.pk).exists()
        assert ReleaseTrack.objects.filter(pk=release_track.pk).exists()
        assert Product.objects.filter(track_id=release_track.pk).exists()
        recording.refresh_from_db()
        assert recording.audio_file.name == original_audio_name
        assert storage.exists(original_audio_name)

    def test_create_cleanup_keeps_recording_that_already_has_audio(
        self,
        artist_user,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """CREATE с сохранённым оригиналом удаляет лишь upload и staging."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Recording._meta.get_field('audio_file')
        monkeypatch.setattr(audio_file_field, 'storage', storage)

        recording, upload = TrackUploadService.create_recording_upload(
            owner=artist_user.artist_profile,
            created_by=artist_user,
            filename='created.flac',
            size=10,
            content_type='audio/flac',
        )
        TrackUploadService.receive_local_file(
            upload=upload,
            uploaded_file=SimpleUploadedFile(
                name='created.flac',
                content=b'0123456789',
                content_type='audio/flac',
            ),
        )
        recording.audio_file.name = 'recordings/original/existing.flac'
        recording.save(update_fields=('audio_file', 'updated_at'))
        TrackUpload.objects.filter(pk=upload.pk).update(
            expires_at=timezone.now() - timedelta(days=2),
        )

        assert storage.exists(upload.staging_key)

        result = TrackUploadCleanupService.cleanup_expired()

        assert result == {
            'deleted': 1,
            'skipped': 0,
            'storage_errors': 0,
        }
        assert not storage.exists(upload.staging_key)
        assert not TrackUpload.objects.filter(pk=upload.pk).exists()
        assert Recording.objects.filter(pk=recording.pk).exists()

    def test_create_cleanup_keeps_recording_with_release_track_and_product(
        self,
        artist_user,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """CREATE с размещением удаляет лишь upload и staging."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Recording._meta.get_field('audio_file')
        monkeypatch.setattr(audio_file_field, 'storage', storage)

        recording, upload = TrackUploadService.create_recording_upload(
            owner=artist_user.artist_profile,
            created_by=artist_user,
            filename='placed.flac',
            size=10,
            content_type='audio/flac',
        )
        TrackUploadService.receive_local_file(
            upload=upload,
            uploaded_file=SimpleUploadedFile(
                name='placed.flac',
                content=b'0123456789',
                content_type='audio/flac',
            ),
        )
        release_track = ReleaseTrackFactory(recording=recording)
        product = ProductService.ensure_commerce(
            release_track,
            validated_data={
                'price': 0,
                'allow_overpay': False,
                'variants': [],
            },
        )
        TrackUpload.objects.filter(pk=upload.pk).update(
            expires_at=timezone.now() - timedelta(days=2),
        )

        assert not recording.audio_file
        assert storage.exists(upload.staging_key)

        result = TrackUploadCleanupService.cleanup_expired()

        assert result == {
            'deleted': 1,
            'skipped': 0,
            'storage_errors': 0,
        }
        assert not storage.exists(upload.staging_key)
        assert not TrackUpload.objects.filter(pk=upload.pk).exists()
        assert Recording.objects.filter(pk=recording.pk).exists()
        assert ReleaseTrack.objects.filter(pk=release_track.pk).exists()
        assert Product.objects.filter(pk=product.pk).exists()

    def test_create_cleanup_keeps_recording_with_active_upload_attempt(
        self,
        artist_user,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """CREATE не удаляет запись с другой действующей попыткой."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Recording._meta.get_field('audio_file')
        monkeypatch.setattr(audio_file_field, 'storage', storage)

        recording, expired_upload = TrackUploadService.create_recording_upload(
            owner=artist_user.artist_profile,
            created_by=artist_user,
            filename='expired.flac',
            size=10,
            content_type='audio/flac',
        )
        TrackUploadService.receive_local_file(
            upload=expired_upload,
            uploaded_file=SimpleUploadedFile(
                name='expired.flac',
                content=b'0123456789',
                content_type='audio/flac',
            ),
        )
        active_upload = TrackUploadService.create_replacement_upload(
            recording=recording,
            filename='active.flac',
            size=10,
            content_type='audio/flac',
        )
        TrackUpload.objects.filter(pk=expired_upload.pk).update(
            expires_at=timezone.now() - timedelta(days=2),
        )

        assert not recording.audio_file
        assert not recording.release_tracks.exists()
        assert storage.exists(expired_upload.staging_key)

        result = TrackUploadCleanupService.cleanup_expired()

        assert result == {
            'deleted': 1,
            'skipped': 0,
            'storage_errors': 0,
        }
        assert not storage.exists(expired_upload.staging_key)
        assert not TrackUpload.objects.filter(pk=expired_upload.pk).exists()
        assert Recording.objects.filter(pk=recording.pk).exists()
        assert TrackUpload.objects.filter(pk=active_upload.pk).exists()
