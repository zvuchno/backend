"""Тесты сервисов загрузки оригинальных файлов треков."""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from store.constants import MAX_AUDIOFILE_SIZE_MB
from store.models import Product, Recording, ReleaseTrack, TrackUpload
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

    @pytest.mark.parametrize(
        'filename',
        (
            'track.jpg',
            'track.mp4',
            'track',
        ),
    )
    def test_rejects_unsupported_extension(self, artist_user, filename):
        """Не создаёт запись для файла с неподдерживаемым расширением."""
        with pytest.raises(ValidationError):
            TrackUploadService.create_recording_upload(
                owner=artist_user.artist_profile,
                created_by=artist_user,
                filename=filename,
                size=10,
            )

        assert Recording.objects.count() == 0
        assert TrackUpload.objects.count() == 0

    def test_rejects_empty_file(self, artist_user):
        """Не создаёт запись для файла нулевого размера."""
        with pytest.raises(ValidationError):
            TrackUploadService.create_recording_upload(
                owner=artist_user.artist_profile,
                created_by=artist_user,
                filename='empty.mp3',
                size=0,
            )

        assert Recording.objects.count() == 0
        assert TrackUpload.objects.count() == 0

    def test_rejects_too_large_file(self, artist_user):
        """Не создаёт запись для файла больше допустимого размера."""
        with pytest.raises(ValidationError):
            TrackUploadService.create_recording_upload(
                owner=artist_user.artist_profile,
                created_by=artist_user,
                filename='huge.flac',
                size=(MAX_AUDIOFILE_SIZE_MB * 1024 * 1024) + 1,
            )

        assert Recording.objects.count() == 0
        assert TrackUpload.objects.count() == 0

    def test_creates_replacement_upload_for_existing_track(self):
        """Создаёт попытку замены файла существующего трека."""
        release_track = ReleaseTrackFactory()
        recording = release_track.recording

        upload = TrackUploadService.create_replacement_upload(
            recording=recording,
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
        recording = release_track.recording

        with pytest.raises(ValidationError):
            TrackUploadService.create_replacement_upload(
                recording=recording,
                filename='new-original.jpg',
                size=10,
                content_type='image/jpeg',
            )

        assert TrackUpload.objects.count() == 0

    def test_creates_replacement_without_release(self):
        """Для замены оригинала не требуется ReleaseTrack."""
        recording = RecordingFactory()

        upload = TrackUploadService.create_replacement_upload(
            recording=recording,
            filename='new-original.flac',
            size=100,
            content_type='audio/flac',
        )

        assert upload.track_id == recording.pk
        assert upload.purpose == TrackUpload.Purpose.REPLACE
        assert upload.status == TrackUpload.Status.INITIATED
        assert not recording.release_tracks.exists()


@pytest.mark.django_db
class TestRecordingUploadCreation:
    """Независимое создание мастер-записи для direct upload."""

    def test_creates_recording_and_upload_only(self, artist_user):
        """Создаёт Recording и TrackUpload без размещения и товара."""
        recording_count = Recording.objects.count()

        recording, upload = TrackUploadService.create_recording_upload(
            owner=artist_user.artist_profile,
            created_by=artist_user,
            filename='01. Intro.flac',
            size=1024,
            content_type='audio/flac',
            name='Intro',
            description='Описание записи',
            isrc='RUA1B2345678',
        )

        assert Recording.objects.count() == recording_count + 1

        recording.refresh_from_db()

        assert recording.owner == artist_user.artist_profile
        assert recording.created_by == artist_user
        assert recording.name == 'Intro'
        assert recording.description == 'Описание записи'
        assert recording.isrc == 'RUA1B2345678'
        assert not recording.audio_file

        assert upload.track_id == recording.pk
        assert upload.purpose == TrackUpload.Purpose.CREATE
        assert upload.status == TrackUpload.Status.INITIATED
        assert upload.expected_size == 1024
        assert upload.original_filename == '01. Intro.flac'
        assert upload.content_type == 'audio/flac'
        assert upload.staging_key.startswith(
            f'staging/track-uploads/{recording.pk}/',
        )

        assert not ReleaseTrack.objects.filter(
            recording=recording,
        ).exists()
        assert Product.objects.count() == 0

    def test_uses_filename_when_name_is_empty(self, artist_user):
        """Подставляет название из имени исходного файла."""
        recording, _ = TrackUploadService.create_recording_upload(
            owner=artist_user.artist_profile,
            created_by=artist_user,
            filename='My New Track.mp3',
            size=100,
            name='  ',
        )

        assert recording.name == 'My New Track'
        assert recording.isrc is None

    def test_does_not_change_existing_release(self, artist_user):
        """Создание записи не меняет состав релиза."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
        )
        existing = ReleaseTrackFactory(
            release=album,
            position=3,
        )

        recording, _ = TrackUploadService.create_recording_upload(
            owner=artist_user.artist_profile,
            created_by=artist_user,
            filename='Another Track.wav',
            size=100,
        )

        assert album.tracks.count() == 1
        assert album.tracks.get().pk == existing.pk
        assert not recording.release_tracks.exists()

    @pytest.mark.parametrize(
        'filename',
        ('track.jpg', 'track.mp4', 'track'),
    )
    def test_rejects_invalid_file(self, artist_user, filename):
        """Неподдерживаемый файл не создаёт запись и upload."""
        recording_count = Recording.objects.count()

        with pytest.raises(ValidationError):
            TrackUploadService.create_recording_upload(
                owner=artist_user.artist_profile,
                created_by=artist_user,
                filename=filename,
                size=100,
            )

        assert Recording.objects.count() == recording_count
        assert TrackUpload.objects.count() == 0

    def test_rejects_invalid_isrc(self, artist_user):
        """Некорректный ISRC не оставляет записей в базе."""
        with pytest.raises(ValidationError):
            TrackUploadService.create_recording_upload(
                owner=artist_user.artist_profile,
                created_by=artist_user,
                filename='track.flac',
                size=100,
                isrc='INVALID',
            )

        assert Recording.objects.count() == 0
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
