"""Тесты завершения загрузки оригинальных файлов треков."""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile

from store.models import Track, TrackUpload
from store.services import ProductService
from store.services.album_archive import AlbumArchiveScheduler
from store.services.track_upload import (
    TrackUploadService,
    TrackUploadStorageError,
    TrackUploadStorageService,
)
from store.tests.factories import AlbumFactory, TrackFactory, make_audio_file


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

    def test_replaces_existing_track_audio_file(
        self,
        settings,
        tmp_path,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Заменяет файл существующего трека без смены позиции и commerce."""
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
        track = TrackFactory(
            album=album,
            position=7,
            audio_file=make_audio_file(
                name='old-original.mp3',
                content=b'old audio content',
            ),
        )

        ProductService.ensure_commerce(
            track,
            validated_data={
                'price': Decimal('250.00'),
                'allow_overpay': True,
                'variants': [],
            },
        )

        old_track_id = track.pk
        old_position = track.position
        old_audio_name = track.audio_file.name
        old_product_id = track.product.id

        new_content = b'new audio content'

        upload = TrackUploadService.create_replacement_upload(
            track=track,
            filename='new-original.flac',
            size=len(new_content),
            content_type='audio/flac',
        )

        received_upload = TrackUploadService.receive_local_file(
            upload=upload,
            uploaded_file=SimpleUploadedFile(
                name='new-original.flac',
                content=new_content,
                content_type='audio/flac',
            ),
        )

        with patch(
            'store.services.track_upload.upload_storage.'
            'TrackGeneratedAudioScheduler.schedule',
            return_value=True,
        ) as mocked_audio_schedule:
            with patch.object(
                AlbumArchiveScheduler,
                'schedule',
                return_value=True,
            ) as mocked_archive_schedule:
                with django_capture_on_commit_callbacks(execute=True):
                    completed_upload = TrackUploadStorageService.complete(
                        upload=received_upload,
                    )

        track.refresh_from_db()
        completed_upload.refresh_from_db()

        assert completed_upload.status == TrackUpload.Status.COMPLETED
        assert completed_upload.uploaded_size == len(new_content)
        assert completed_upload.completed_at is not None
        assert completed_upload.error == ''

        assert track.pk == old_track_id
        assert track.position == old_position
        assert track.product.id == old_product_id
        assert track.product.price == Decimal('250.00')
        assert track.product.allow_overpay is True

        assert track.audio_file.name != old_audio_name
        assert track.audio_file.name.startswith(
            f'albums/{album.pk}/tracks/original/',
        )
        assert track.audio_file.name.endswith('.flac')

        assert storage.exists(track.audio_file.name)
        assert storage.exists(old_audio_name)
        assert not storage.exists(upload.staging_key)

        with storage.open(track.audio_file.name, 'rb') as audio_file:
            assert audio_file.read() == new_content

        mocked_audio_schedule.assert_called_once_with(track)
        mocked_archive_schedule.assert_called_once_with(album)

    def test_keeps_old_audio_file_when_replacement_staging_is_missing(
        self,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """Не меняет текущий файл, если staging-файл замены отсутствует."""
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

        track = TrackFactory(
            audio_file=make_audio_file(
                name='old-original.mp3',
                content=b'old audio content',
            ),
        )

        old_audio_name = track.audio_file.name

        upload = TrackUploadService.create_replacement_upload(
            track=track,
            filename='missing-new-original.flac',
            size=10,
            content_type='audio/flac',
        )

        with pytest.raises(
            TrackUploadStorageError,
            match='Временный файл загрузки не найден',
        ):
            TrackUploadStorageService.complete(upload=upload)

        track.refresh_from_db()
        upload.refresh_from_db()

        assert track.audio_file.name == old_audio_name
        assert storage.exists(old_audio_name)

        assert upload.status == TrackUpload.Status.INITIATED
        assert upload.completed_at is None

    def test_complete_is_idempotent_for_completed_upload(
        self,
        settings,
        tmp_path,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Повторный complete для завершённой загрузки возвращает успех."""
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
            filename='track.flac',
            size=len(file_content),
            content_type='audio/flac',
        )

        upload = TrackUploadService.receive_local_file(
            upload=upload,
            uploaded_file=SimpleUploadedFile(
                name='track.flac',
                content=file_content,
                content_type='audio/flac',
            ),
        )

        with patch(
            'store.services.track_upload.upload_storage.'
            'TrackGeneratedAudioScheduler.schedule',
        ) as mocked_audio_schedule:
            with patch.object(
                AlbumArchiveScheduler,
                'schedule',
                return_value=True,
            ) as mocked_archive_schedule:
                with django_capture_on_commit_callbacks(execute=True):
                    completed_upload = TrackUploadStorageService.complete(
                        upload=upload,
                    )

                track.refresh_from_db()
                first_audio_file_name = track.audio_file.name

                second_completed_upload = TrackUploadStorageService.complete(
                    upload=completed_upload,
                )

        track.refresh_from_db()
        second_completed_upload.refresh_from_db()

        assert second_completed_upload.status == TrackUpload.Status.COMPLETED
        assert track.audio_file.name == first_audio_file_name
        assert not storage.exists(upload.staging_key)

        assert mocked_audio_schedule.call_count == 1
        assert mocked_archive_schedule.call_count == 1
