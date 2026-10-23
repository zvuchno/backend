"""Тесты сервисов загрузки оригинальных файлов треков."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from store.constants import MAX_AUDIOFILE_SIZE_MB
from store.models import TrackUpload
from store.services.track_upload import (
    TrackUploadService,
    TrackUploadTransportService,
)
from store.tests.factories import (
    AlbumFactory,
    RecordingFactory,
    ReleaseTrackFactory,
)


@pytest.mark.django_db
class TestTrackUploadService:
    """Тесты подготовки треков к загрузке."""

    def test_creates_pending_track_and_upload(self):
        """Создаёт Recording, ReleaseTrack, Product и upload записи."""
        album = AlbumFactory()

        release_track, upload = TrackUploadService.create_pending_track(
            album=album,
            created_by=album.created_by,
            filename='01. Intro.flac',
            size=10,
            content_type='audio/flac',
        )
        recording = release_track.recording

        assert release_track.release == album
        assert release_track.position == 1
        assert release_track.is_active is True
        assert recording.owner == album.artist
        assert recording.name == '01. Intro'
        assert not recording.audio_file

        assert release_track.product.price == Decimal('0.00')
        assert release_track.product.variants.count() == 1

        assert upload.track == recording
        assert upload.status == TrackUpload.Status.INITIATED
        assert upload.original_filename == '01. Intro.flac'
        assert upload.expected_size == 10
        assert upload.content_type == 'audio/flac'
        assert upload.staging_key.startswith(
            f'staging/track-uploads/{recording.pk}/',
        )

    def test_pending_release_track_gets_next_position_immediately(self):
        """Новое размещение сразу получает следующую позицию в релизе."""
        album = AlbumFactory()

        ReleaseTrackFactory(
            release=album,
            position=4,
        )

        release_track, _ = TrackUploadService.create_pending_track(
            album=album,
            created_by=album.created_by,
            filename='Next.mp3',
            size=10,
        )

        assert release_track.position == 5

    @pytest.mark.parametrize(
        'filename',
        (
            'track.jpg',
            'track.mp4',
            'track',
        ),
    )
    def test_rejects_unsupported_extension(self, filename):
        """Не создаёт трек для файла с неподдерживаемым расширением."""
        album = AlbumFactory()

        with pytest.raises(ValidationError):
            TrackUploadService.create_pending_track(
                album=album,
                created_by=album.created_by,
                filename=filename,
                size=10,
            )

        assert album.tracks.count() == 0
        assert TrackUpload.objects.count() == 0

    def test_rejects_empty_file(self):
        """Не создаёт трек для файла нулевого размера."""
        album = AlbumFactory()

        with pytest.raises(ValidationError):
            TrackUploadService.create_pending_track(
                album=album,
                created_by=album.created_by,
                filename='empty.mp3',
                size=0,
            )

        assert album.tracks.count() == 0
        assert TrackUpload.objects.count() == 0

    def test_rejects_too_large_file(self):
        """Не создаёт трек для файла больше допустимого размера."""
        album = AlbumFactory()

        with pytest.raises(ValidationError):
            TrackUploadService.create_pending_track(
                album=album,
                created_by=album.created_by,
                filename='huge.flac',
                size=(MAX_AUDIOFILE_SIZE_MB * 1024 * 1024) + 1,
            )

        assert album.tracks.count() == 0
        assert TrackUpload.objects.count() == 0

    def test_creates_pending_track_with_api_metadata(self):
        """Создаёт черновой трек с метаданными из API-формы."""
        album = AlbumFactory()

        release_track, upload = TrackUploadService.create_pending_track(
            album=album,
            created_by=album.created_by,
            filename='01. Original name.flac',
            size=10,
            content_type='audio/flac',
            name='Новое название',
            description='Описание трека.',
            price=Decimal('150.00'),
            allow_overpay=True,
            isrc='RUA1B2345678',
        )
        recording = release_track.recording

        assert release_track.release == album
        assert release_track.position == 1
        assert release_track.is_active is True
        assert recording.name == 'Новое название'
        assert recording.description == 'Описание трека.'
        assert recording.isrc == 'RUA1B2345678'
        assert not recording.audio_file

        assert release_track.product.price == Decimal('150.00')
        assert release_track.product.allow_overpay is True
        assert release_track.product.variants.count() == 1

        assert upload.track == recording
        assert upload.status == TrackUpload.Status.INITIATED
        assert upload.original_filename == '01. Original name.flac'

    def test_creates_replacement_upload_for_existing_track(self):
        """Создаёт попытку замены файла существующего трека."""
        release_track = ReleaseTrackFactory()
        recording = release_track.recording

        upload = TrackUploadService.create_replacement_upload(
            track=release_track,
            filename='new-original.flac',
            size=10,
            content_type='audio/flac',
        )

        release_track.refresh_from_db()
        recording.refresh_from_db()

        assert upload.track == recording
        assert upload.purpose == TrackUpload.Purpose.REPLACE
        assert upload.status == TrackUpload.Status.INITIATED
        assert upload.original_filename == 'new-original.flac'
        assert upload.expected_size == 10
        assert upload.content_type == 'audio/flac'
        assert upload.staging_key.startswith(
            f'staging/track-uploads/{recording.pk}/',
        )

        assert release_track.position is not None
        assert recording.audio_file

    def test_replacement_upload_rejects_invalid_file(self):
        """Не создаёт попытку замены для неподдерживаемого файла."""
        release_track = ReleaseTrackFactory()

        with pytest.raises(ValidationError):
            TrackUploadService.create_replacement_upload(
                track=release_track,
                filename='new-original.jpg',
                size=10,
                content_type='image/jpeg',
            )

        assert TrackUpload.objects.count() == 0


@pytest.mark.django_db
class TestTrackUploadTransportService:
    """Тесты генерации инструкций транспорта загрузки."""

    def test_returns_local_instruction_when_s3_is_disabled(
        self,
        settings,
    ):
        """Возвращает local endpoint для загрузки файла."""
        settings.USE_S3_MEDIA = False

        recording = RecordingFactory()
        upload = TrackUpload.objects.create(
            track=recording,
            staging_key='staging/track-uploads/1/test.flac',
            original_filename='test.flac',
            expected_size=10,
            content_type='audio/flac',
            expires_at=timezone.now() + timedelta(hours=1),
        )

        result = TrackUploadTransportService.create_instruction(
            upload=upload,
            local_upload_url='/admin/store/track-uploads/1/file/',
        )

        assert result.method == 'POST'
        assert result.url == '/admin/store/track-uploads/1/file/'
        assert result.headers == {}
        assert result.fields == {}
        assert result.file_field_name == 'file'
        assert result.expires_at == upload.expires_at

    @patch.object(TrackUploadTransportService, '_get_client')
    def test_creates_presigned_post_for_private_storage(
        self,
        mocked_get_client,
        settings,
    ):
        """Создаёт presigned POST-инструкцию для private bucket."""
        settings.USE_S3_MEDIA = True
        settings.AWS_PRIVATE_STORAGE_BUCKET_NAME = 'private-bucket'
        settings.AWS_ACCESS_KEY_ID = 'test-key'
        settings.AWS_SECRET_ACCESS_KEY = 'test-secret'
        settings.AWS_S3_ENDPOINT_URL = 'https://s3.test'
        settings.AWS_S3_REGION_NAME = 'us-east-1'
        settings.MEDIA_LOCATION = 'media'

        client = Mock()
        client.generate_presigned_post.return_value = {
            'url': 'https://storage.test/presigned-post-upload',
            'fields': {
                'key': 'media/staging/track-uploads/1/test.flac',
                'Content-Type': 'audio/flac',
            },
        }
        mocked_get_client.return_value = client

        fixed_now = timezone.now()

        with patch(
            'django.utils.timezone.now',
            return_value=fixed_now,
        ):
            recording = RecordingFactory()
            upload = TrackUpload.objects.create(
                track=recording,
                staging_key='staging/track-uploads/1/test.flac',
                original_filename='test.flac',
                expected_size=10,
                content_type='audio/flac',
                expires_at=fixed_now + timedelta(hours=1),
            )

            result = TrackUploadTransportService.create_instruction(
                upload=upload,
                local_upload_url='/admin/store/track-uploads/1/file/',
            )

        assert result.method == 'POST'
        assert result.url == 'https://storage.test/presigned-post-upload'
        assert result.headers == {}
        assert result.fields == {
            'key': 'media/staging/track-uploads/1/test.flac',
            'Content-Type': 'audio/flac',
        }
        assert result.file_field_name == 'file'
        assert result.expires_at == upload.expires_at

        client.generate_presigned_post.assert_called_once_with(
            Bucket='private-bucket',
            Key='media/staging/track-uploads/1/test.flac',
            Fields={
                'Content-Type': 'audio/flac',
            },
            Conditions=[
                [
                    'content-length-range',
                    10,
                    10,
                ],
                {
                    'Content-Type': 'audio/flac',
                },
            ],
            ExpiresIn=3600,
        )
