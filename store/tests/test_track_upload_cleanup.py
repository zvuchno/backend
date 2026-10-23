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
from store.tests.factories import AlbumFactory, ReleaseTrackFactory


@pytest.mark.django_db
class TestTrackUploadCleanupService:
    """Тесты уборки технических треков и staging-файлов."""

    def test_deletes_abandoned_upload_and_pending_track(
        self,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """Удаляет staging, ReleaseTrack, Product, Recording и upload."""
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

        album = AlbumFactory()
        file_content = b'test audio content'

        release_track, upload = TrackUploadService.create_pending_track(
            album=album,
            created_by=album.created_by,
            filename='abandoned.flac',
            size=len(file_content),
            content_type='audio/flac',
        )
        recording = release_track.recording

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
        assert Product.objects.filter(track_id=release_track.pk).exists()

        result = TrackUploadCleanupService.cleanup_expired()

        assert result == {
            'deleted': 1,
            'skipped': 0,
            'storage_errors': 0,
        }
        assert not storage.exists(upload.staging_key)
        assert not ReleaseTrack.objects.filter(pk=release_track.pk).exists()
        assert not Recording.objects.filter(pk=recording.pk).exists()
        assert not TrackUpload.objects.filter(pk=upload.pk).exists()
        assert not Product.objects.filter(track_id=release_track.pk).exists()

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
        audio_file_field = Recording._meta.get_field('audio_file')

        monkeypatch.setattr(
            audio_file_field,
            'storage',
            storage,
        )

        album = AlbumFactory()

        release_track, upload = TrackUploadService.create_pending_track(
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
        assert ReleaseTrack.objects.filter(pk=release_track.pk).exists()
        assert Recording.objects.filter(
            pk=release_track.recording_id,
        ).exists()
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
        audio_file_field = Recording._meta.get_field('audio_file')

        monkeypatch.setattr(
            audio_file_field,
            'storage',
            storage,
        )

        album = AlbumFactory()

        release_track, upload = TrackUploadService.create_pending_track(
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
        assert ReleaseTrack.objects.filter(pk=release_track.pk).exists()
        assert Recording.objects.filter(
            pk=release_track.recording_id,
        ).exists()
        assert Product.objects.filter(track_id=release_track.pk).exists()
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
            track=release_track,
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

        album = AlbumFactory()
        release_track, upload = TrackUploadService.create_pending_track(
            album=album,
            created_by=album.created_by,
            filename='created.flac',
            size=10,
            content_type='audio/flac',
        )
        recording = release_track.recording
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
        assert ReleaseTrack.objects.filter(pk=release_track.pk).exists()
        assert Product.objects.filter(track_id=release_track.pk).exists()
