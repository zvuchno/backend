"""Тесты очистки заброшенных загрузок оригинальных файлов треков."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from store.models import Product, Track, TrackUpload
from store.services.track_upload import (
    TrackUploadCleanupService,
    TrackUploadService,
)
from store.tests.factories import AlbumFactory


@pytest.mark.django_db
class TestTrackUploadCleanupService:
    """Тесты уборки технических треков и staging-файлов."""

    def test_deletes_abandoned_upload_and_pending_track(
        self,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """Удаляет staging-файл, технический Track и его Product."""
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
            created_by=album.created_by,
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
        assert Product.objects.filter(track_id=track.pk).exists()

        result = TrackUploadCleanupService.cleanup_expired()

        assert result == {
            'deleted': 1,
            'skipped': 0,
            'storage_errors': 0,
        }
        assert not storage.exists(upload.staging_key)
        assert not Track.objects.filter(pk=track.pk).exists()
        assert not TrackUpload.objects.filter(pk=upload.pk).exists()
        assert not Product.objects.filter(track_id=track.pk).exists()

    def test_keeps_recent_pending_upload(
        self,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """Не удаляет технический трек до истечения срока очистки."""
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

        track, upload = TrackUploadService.create_pending_track(
            album=album,
            created_by=album.created_by,
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
        assert Track.objects.filter(pk=track.pk).exists()
        assert TrackUpload.objects.filter(pk=upload.pk).exists()

    def test_keeps_upload_when_staging_cleanup_fails(
        self,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """Не удаляет БД-черновик, если staging-файл удалить не удалось."""
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

        track, upload = TrackUploadService.create_pending_track(
            album=album,
            created_by=album.created_by,
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
        assert Track.objects.filter(pk=track.pk).exists()
        assert TrackUpload.objects.filter(pk=upload.pk).exists()
