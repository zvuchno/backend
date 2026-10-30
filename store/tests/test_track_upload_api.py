"""Тесты API прямой загрузки оригинальных файлов треков."""

from datetime import timedelta
from decimal import Decimal
from http import HTTPStatus
from unittest.mock import call, patch

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from store.models import Product, Recording, ReleaseTrack, TrackUpload
from store.services import TrackService
from store.services.album_archive import AlbumArchiveScheduler
from store.services.track_upload import (
    TrackUploadStorageService,
    UploadInstruction,
)
from store.tests.factories import (
    AlbumFactory,
    RecordingFactory,
    ReleaseTrackFactory,
)


@pytest.mark.django_db
class TestTrackUploadApi:
    """Тесты API загрузки оригинальных файлов треков."""

    @patch(
        'store.views.track_upload.'
        'TrackUploadTransportService.create_instruction',
    )
    def test_initiates_track_upload_with_metadata(
        self,
        mocked_create_instruction,
        artist_client,
        artist_user,
    ):
        """Создаёт черновой трек с метаданными и возвращает transport."""
        expires_at = timezone.now() + timedelta(hours=1)

        mocked_create_instruction.return_value = UploadInstruction(
            method='POST',
            url='https://storage.test/upload',
            headers={},
            fields={
                'key': 'media/staging/track-uploads/1/test.flac',
                'Content-Type': 'audio/flac',
            },
            file_field_name='file',
            expires_at=expires_at,
        )

        initial_tracks = ReleaseTrack.objects.count()
        initial_products = Product.objects.count()

        url = reverse('api:store:track-upload-initiate')

        response = artist_client.post(
            url,
            data={
                'artist': artist_user.artist_profile.pk,
                'filename': '01 Original.flac',
                'size': 123,
                'content_type': 'audio/flac',
                'name': 'Новое название',
                'description': 'Описание трека.',
                'isrc': 'RUA1B2345678',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        data = response.json()
        recording = Recording.objects.get(
            pk=data['recording']['id'],
        )
        upload = TrackUpload.objects.get(
            pk=data['upload']['id'],
        )

        assert recording.name == 'Новое название'
        assert recording.description == 'Описание трека.'
        assert recording.isrc == 'RUA1B2345678'
        assert not recording.audio_file
        assert recording.owner == artist_user.artist_profile
        assert not recording.release_tracks.exists()
        assert ReleaseTrack.objects.count() == initial_tracks
        assert Product.objects.count() == initial_products

        assert data['recording'] == {
            'id': recording.pk,
            'name': 'Новое название',
            'description': 'Описание трека.',
            'isrc': 'RUA1B2345678',
        }

        assert upload.track == recording
        assert upload.staging_key.startswith(
            f'staging/track-uploads/{recording.pk}/',
        )
        assert upload.status == TrackUpload.Status.INITIATED
        assert upload.original_filename == '01 Original.flac'
        assert upload.expected_size == 123
        assert upload.content_type == 'audio/flac'
        assert data['upload']['id'] == upload.pk
        assert data['upload']['status'] == TrackUpload.Status.INITIATED
        assert data['upload']['uploaded_size'] is None
        assert data['upload']['completed_at'] is None
        complete_path = reverse(
            'api:store:track-upload-complete',
            args=(upload.pk,),
        )
        assert data['upload']['complete_url'].endswith(complete_path)
        assert data['upload']['transport'] == {
            'method': 'POST',
            'url': 'https://storage.test/upload',
            'headers': {},
            'fields': {
                'key': 'media/staging/track-uploads/1/test.flac',
                'Content-Type': 'audio/flac',
            },
            'file_field_name': 'file',
        }

        mocked_create_instruction.assert_called_once()

    def test_rejects_track_upload_for_foreign_artist(
        self,
        artist_client,
        other_artist_user,
    ):
        """Не позволяет создавать записи для неподконтрольного артиста."""
        initial_recordings = Recording.objects.count()

        url = reverse('api:store:track-upload-initiate')

        response = artist_client.post(
            url,
            data={
                'artist': other_artist_user.artist_profile.pk,
                'filename': 'track.flac',
                'size': 123,
                'content_type': 'audio/flac',
                'name': 'Track',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert Recording.objects.count() == initial_recordings
        assert TrackUpload.objects.count() == 0

    def test_returns_validation_error_for_invalid_file(
        self,
        artist_client,
        artist_user,
    ):
        """Не создаёт мастер-запись для неподдерживаемого файла."""
        url = reverse('api:store:track-upload-initiate')

        response = artist_client.post(
            url,
            data={
                'filename': 'cover.jpg',
                'size': 123,
                'content_type': 'image/jpeg',
                'name': 'Invalid',
                'artist': artist_user.artist_profile.pk,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert Recording.objects.count() == 0
        assert ReleaseTrack.objects.count() == 0
        assert TrackUpload.objects.count() == 0

    def test_completes_local_upload_flow(
        self,
        artist_client,
        artist_user,
        settings,
        tmp_path,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Создаёт Recording, загружает оригинал и завершает upload."""
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

        initial_tracks = ReleaseTrack.objects.count()
        initial_products = Product.objects.count()

        file_content = b'test audio content'

        initiate_url = reverse(
            'api:store:track-upload-initiate',
        )

        initiate_response = artist_client.post(
            initiate_url,
            data={
                'artist': artist_user.artist_profile.pk,
                'filename': '01 Intro.flac',
                'size': len(file_content),
                'content_type': 'audio/flac',
                'name': 'Intro',
                'description': 'Описание.',
            },
            format='json',
        )

        assert initiate_response.status_code == HTTPStatus.CREATED

        initiate_data = initiate_response.json()
        recording_id = initiate_data['recording']['id']
        upload_id = initiate_data['upload']['id']
        transport = initiate_data['upload']['transport']

        recording = Recording.objects.get(pk=recording_id)

        assert recording.owner == artist_user.artist_profile
        assert recording.name == 'Intro'
        assert not recording.audio_file
        assert not recording.release_tracks.exists()

        assert ReleaseTrack.objects.count() == initial_tracks
        assert Product.objects.count() == initial_products

        assert transport['method'] == 'POST'
        assert transport['fields'] == {}
        assert transport['headers'] == {}
        assert transport['file_field_name'] == 'file'
        assert transport['url'].endswith(
            reverse(
                'api:store:track-upload-receive-file',
                args=(upload_id,),
            ),
        )

        upload_response = artist_client.post(
            transport['url'],
            data={
                'file': SimpleUploadedFile(
                    name='01 Intro.flac',
                    content=file_content,
                    content_type='audio/flac',
                ),
            },
            format='multipart',
        )

        assert upload_response.status_code == HTTPStatus.OK

        assert upload_response.json() == {
            'upload': {
                'id': upload_id,
                'status': TrackUpload.Status.UPLOADED,
                'uploaded_size': len(file_content),
            },
        }

        upload = TrackUpload.objects.get(pk=upload_id)

        assert upload.track_id == recording_id
        assert upload.purpose == TrackUpload.Purpose.CREATE
        assert storage.exists(upload.staging_key)

        complete_url = initiate_data['upload']['complete_url']

        assert complete_url.endswith(
            reverse(
                'api:store:track-upload-complete',
                args=(upload_id,),
            ),
        )
        assert 'track_id=' not in complete_url

        with patch(
            'store.services.track_upload.upload_storage.'
            'TrackGeneratedAudioScheduler.schedule',
        ) as mocked_schedule:
            with patch.object(
                AlbumArchiveScheduler,
                'schedule_by_id',
            ) as mocked_archive_schedule:
                with django_capture_on_commit_callbacks(execute=True):
                    complete_response = artist_client.post(complete_url)

        assert complete_response.status_code == HTTPStatus.OK

        complete_data = complete_response.json()

        assert complete_data['recording'] == {
            'id': recording_id,
            'name': 'Intro',
            'description': 'Описание.',
            'isrc': None,
        }

        assert complete_data['upload']['id'] == upload_id
        assert complete_data['upload']['status'] == (
            TrackUpload.Status.COMPLETED
        )
        assert complete_data['upload']['uploaded_size'] == len(file_content)
        assert complete_data['upload']['completed_at'] is not None

        recording.refresh_from_db()
        upload.refresh_from_db()

        assert upload.status == TrackUpload.Status.COMPLETED
        assert recording.audio_file
        assert recording.audio_file.name.startswith(
            'recordings/original/',
        )

        assert storage.exists(recording.audio_file.name)

        with storage.open(recording.audio_file.name, 'rb') as stored_file:
            assert stored_file.read() == file_content

        assert not storage.exists(upload.staging_key)

        assert ReleaseTrack.objects.count() == initial_tracks
        assert Product.objects.count() == initial_products

        mocked_schedule.assert_called_once_with(recording)
        mocked_archive_schedule.assert_not_called()

    def test_cannot_complete_foreign_upload(
        self,
        artist_client,
    ):
        """Не позволяет завершить чужую загрузку трека."""
        recording = RecordingFactory()
        upload = TrackUpload.objects.create(
            track=recording,
            staging_key='staging/track-uploads/1/test.flac',
            original_filename='test.flac',
            expected_size=10,
            content_type='audio/flac',
            expires_at=timezone.now() + timedelta(hours=1),
        )

        url = reverse(
            'api:store:track-upload-complete',
            args=(upload.pk,),
        )

        response = artist_client.post(url)

        assert response.status_code == HTTPStatus.FORBIDDEN

    @patch(
        'store.views.track_upload.'
        'TrackUploadTransportService.create_instruction',
    )
    def test_initiates_recording_file_replacement_upload(
        self,
        mocked_create_instruction,
        artist_client,
        artist_user,
    ):
        """Создаёт попытку замены файла существующей записи."""
        expires_at = timezone.now() + timedelta(hours=1)

        mocked_create_instruction.return_value = UploadInstruction(
            method='POST',
            url='https://storage.test/upload',
            headers={},
            fields={
                'key': 'media/staging/track-uploads/1/new.flac',
                'Content-Type': 'audio/flac',
            },
            file_field_name='file',
            expires_at=expires_at,
        )

        album = AlbumFactory(artist=artist_user.artist_profile)
        release_track = ReleaseTrackFactory(
            release=album,
            position=5,
        )

        url = reverse(
            'api:store:track-upload-replace-initiate',
        )

        response = artist_client.post(
            url,
            data={
                'recording_id': release_track.recording_id,
                'filename': 'new-original.flac',
                'size': 123,
                'content_type': 'audio/flac',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        data = response.json()

        upload = TrackUpload.objects.get(pk=data['upload']['id'])
        release_track.refresh_from_db()

        assert upload.track == release_track.recording
        assert upload.purpose == TrackUpload.Purpose.REPLACE
        assert upload.status == TrackUpload.Status.INITIATED
        assert upload.original_filename == 'new-original.flac'
        assert upload.expected_size == 123
        assert upload.content_type == 'audio/flac'

        assert data['recording'] == {
            'id': release_track.recording.pk,
            'name': release_track.recording.name,
            'description': release_track.recording.description,
            'isrc': release_track.recording.isrc,
        }

        assert data['upload']['complete_url'].endswith(
            reverse(
                'api:store:track-upload-complete',
                args=(upload.pk,),
            ),
        )
        assert data['upload']['status'] == TrackUpload.Status.INITIATED
        assert data['upload']['transport'] == {
            'method': 'POST',
            'url': 'https://storage.test/upload',
            'headers': {},
            'fields': {
                'key': 'media/staging/track-uploads/1/new.flac',
                'Content-Type': 'audio/flac',
            },
            'file_field_name': 'file',
        }
        assert release_track.position == 5
        assert upload.track_id == release_track.recording_id
        assert upload.purpose == TrackUpload.Purpose.REPLACE

        mocked_create_instruction.assert_called_once()

    def test_rejects_file_replacement_for_foreign_recording(
        self,
        artist_client,
    ):
        """Не позволяет артисту заменить файл чужой записи."""
        release_track = ReleaseTrackFactory()

        url = reverse(
            'api:store:track-upload-replace-initiate',
        )

        response = artist_client.post(
            url,
            data={
                'recording_id': release_track.recording_id,
                'filename': 'new-original.flac',
                'size': 123,
                'content_type': 'audio/flac',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert TrackUpload.objects.count() == 0

    def test_initiates_replacement_without_release(
        self,
        artist_client,
        artist_user,
        settings,
    ):
        """Замена оригинала не требует размещения в релизе."""
        settings.USE_S3_MEDIA = False

        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
        )

        assert not recording.release_tracks.exists()

        url = reverse(
            'api:store:track-upload-replace-initiate',
        )

        response = artist_client.post(
            url,
            data={
                'recording_id': recording.pk,
                'filename': 'new-master.flac',
                'size': 123,
                'content_type': 'audio/flac',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        data = response.json()
        upload = TrackUpload.objects.get(
            pk=data['upload']['id'],
        )

        assert data['recording']['id'] == recording.pk
        assert upload.track_id == recording.pk
        assert upload.purpose == TrackUpload.Purpose.REPLACE
        assert upload.status == TrackUpload.Status.INITIATED

        assert Recording.objects.filter(
            pk=recording.pk,
        ).exists()

        assert not recording.release_tracks.exists()
        assert ReleaseTrack.objects.count() == 0

        assert data['upload']['complete_url'].endswith(
            reverse(
                'api:store:track-upload-complete',
                args=(upload.pk,),
            ),
        )

    def test_replaces_original_shared_by_two_releases(
        self,
        artist_client,
        artist_user,
        settings,
        tmp_path,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Замена оригинала сохраняет размещения и обновляет оба архива."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        monkeypatch.setattr(
            Recording._meta.get_field('audio_file'),
            'storage',
            storage,
        )

        # Существующий оригинал мастер-записи.
        old_content = b'old original audio'
        old_key = storage.save(
            'recordings/original/old-master.flac',
            ContentFile(old_content),
        )

        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
            audio_file=old_key,
        )
        recording.file_hash = 'a' * 64
        recording.save(update_fields=('file_hash',))

        # Одна мастер-запись используется в двух разных релизах.
        first_album = AlbumFactory(
            artist=artist_user.artist_profile,
            created_by=artist_user,
            is_published=False,
        )
        second_album = AlbumFactory(
            artist=artist_user.artist_profile,
            created_by=artist_user,
            is_published=False,
        )

        first_track = TrackService.add_recording(
            release=first_album,
            recording=recording,
            user=artist_user,
            price=Decimal('100.00'),
            allow_overpay=False,
        )
        second_track = TrackService.add_recording(
            release=second_album,
            recording=recording,
            user=artist_user,
            price=Decimal('250.00'),
            allow_overpay=True,
        )

        initial_positions = (
            first_track.position,
            second_track.position,
        )
        initial_track_count = ReleaseTrack.objects.count()
        initial_product_count = Product.objects.count()

        # Инициализируем замену непосредственно по recording_id.
        initiate_response = artist_client.post(
            reverse('api:store:track-upload-replace-initiate'),
            data={
                'recording_id': recording.pk,
                'filename': 'new-master.flac',
                'size': len(b'new original audio content'),
                'content_type': 'audio/flac',
            },
            format='json',
        )

        assert initiate_response.status_code == HTTPStatus.CREATED

        initiate_data = initiate_response.json()
        upload_id = initiate_data['upload']['id']
        transport = initiate_data['upload']['transport']

        assert initiate_data['recording']['id'] == recording.pk

        upload = TrackUpload.objects.get(pk=upload_id)

        assert upload.track_id == recording.pk
        assert upload.purpose == TrackUpload.Purpose.REPLACE

        # До завершения загрузки оригинал не должен измениться.
        recording.refresh_from_db()
        assert recording.audio_file.name == old_key

        # Передаём новый оригинал в локальное staging-хранилище.
        new_content = b'new original audio content'

        upload_response = artist_client.post(
            transport['url'],
            data={
                'file': SimpleUploadedFile(
                    name='new-master.flac',
                    content=new_content,
                    content_type='audio/flac',
                ),
            },
            format='multipart',
        )

        assert upload_response.status_code == HTTPStatus.OK
        assert storage.exists(upload.staging_key)

        # Повторный complete не копирует файл и не планирует задачи заново.
        complete_url = initiate_data['upload']['complete_url']
        with patch.object(
            TrackUploadStorageService,
            '_copy_local_staging_to_final',
            wraps=(TrackUploadStorageService._copy_local_staging_to_final),
        ) as mocked_copy:
            with patch(
                'store.services.track_upload.upload_storage.'
                'TrackGeneratedAudioScheduler.schedule',
            ) as mocked_audio_schedule:
                with patch.object(
                    AlbumArchiveScheduler,
                    'schedule_by_id',
                ) as mocked_archive_schedule:
                    with django_capture_on_commit_callbacks(execute=True):
                        complete_response = artist_client.post(complete_url)
                        repeated_response = artist_client.post(complete_url)

        assert complete_response.status_code == HTTPStatus.OK
        assert repeated_response.status_code == HTTPStatus.OK
        assert repeated_response.json() == complete_response.json()

        # Мастер-запись получила новый оригинал.
        recording.refresh_from_db()
        upload.refresh_from_db()

        assert upload.status == TrackUpload.Status.COMPLETED
        assert recording.audio_file.name != old_key
        assert recording.file_hash == ''

        assert storage.exists(recording.audio_file.name)

        with storage.open(recording.audio_file.name, 'rb') as stored_file:
            assert stored_file.read() == new_content

        assert not storage.exists(upload.staging_key)

        # Оба размещения и их коммерческие данные сохранились.
        first_track.refresh_from_db()
        second_track.refresh_from_db()

        assert first_track.recording_id == recording.pk
        assert second_track.recording_id == recording.pk

        assert (
            first_track.position,
            second_track.position,
        ) == initial_positions

        assert first_track.is_active is True
        assert second_track.is_active is True

        assert first_track.product.price == Decimal('100.00')
        assert first_track.product.allow_overpay is False

        assert second_track.product.price == Decimal('250.00')
        assert second_track.product.allow_overpay is True

        assert ReleaseTrack.objects.count() == initial_track_count
        assert Product.objects.count() == initial_product_count

        # Обрабатывается одна запись, но обновляются оба архива.
        mocked_copy.assert_called_once()
        mocked_audio_schedule.assert_called_once_with(recording)

        assert mocked_archive_schedule.call_count == 2
        mocked_archive_schedule.assert_has_calls(
            [
                call(first_album.pk),
                call(second_album.pk),
            ],
            any_order=True,
        )
