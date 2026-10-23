"""Тесты API прямой загрузки оригинальных файлов треков."""

from datetime import timedelta
from decimal import Decimal
from http import HTTPStatus
from unittest.mock import patch

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from store.models import Recording, ReleaseTrack, TrackUpload
from store.services.album_archive import AlbumArchiveScheduler
from store.services.track_upload import UploadInstruction
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

        album = AlbumFactory(artist=artist_user.artist_profile)
        RecordingFactory()

        url = reverse(
            'api:store:track-upload-initiate',
            args=(album.pk,),
        )

        response = artist_client.post(
            url,
            data={
                'filename': '01 Original.flac',
                'size': 123,
                'content_type': 'audio/flac',
                'name': 'Новое название',
                'description': 'Описание трека.',
                'price': '150.00',
                'allow_overpay': True,
                'isrc': 'RUA1B2345678',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        data = response.json()

        release_track = ReleaseTrack.objects.select_related(
            'recording',
        ).get(pk=data['track']['id'])
        recording = release_track.recording
        upload = TrackUpload.objects.get(pk=data['upload']['id'])

        assert release_track.release == album
        assert release_track.position == 1
        assert recording.name == 'Новое название'
        assert recording.description == 'Описание трека.'
        assert recording.isrc == 'RUA1B2345678'
        assert not recording.audio_file

        assert release_track.product.price == Decimal('150.00')
        assert release_track.product.allow_overpay is True
        assert release_track.product.variants.count() == 1

        assert upload.track == recording
        assert upload.staging_key.startswith(
            f'staging/track-uploads/{recording.pk}/',
        )
        assert upload.status == TrackUpload.Status.INITIATED
        assert upload.original_filename == '01 Original.flac'
        assert upload.expected_size == 123
        assert upload.content_type == 'audio/flac'

        assert data['track'] == {
            'id': release_track.pk,
            'name': 'Новое название',
            'description': 'Описание трека.',
            'position': 1,
            'price': '150.00',
            'allow_overpay': True,
            'isrc': 'RUA1B2345678',
        }
        assert data['track']['id'] != recording.pk

        assert data['upload']['id'] == upload.pk
        assert data['upload']['status'] == TrackUpload.Status.INITIATED
        assert data['upload']['uploaded_size'] is None
        assert data['upload']['completed_at'] is None
        complete_path = reverse(
            'api:store:track-upload-complete',
            args=(upload.pk,),
        )
        assert data['upload']['complete_url'].endswith(
            f'{complete_path}?track_id={release_track.pk}',
        )
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

    def test_rejects_track_upload_for_foreign_album(
        self,
        artist_client,
    ):
        """Не позволяет артисту загружать трек в чужой альбом."""
        album = AlbumFactory()

        url = reverse(
            'api:store:track-upload-initiate',
            args=(album.pk,),
        )

        response = artist_client.post(
            url,
            data={
                'filename': 'track.flac',
                'size': 123,
                'content_type': 'audio/flac',
                'name': 'Track',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert TrackUpload.objects.count() == 0

    def test_returns_validation_error_for_invalid_file(
        self,
        artist_client,
        artist_user,
    ):
        """Не создаёт черновой трек для неподдерживаемого файла."""
        album = AlbumFactory(artist=artist_user.artist_profile)

        url = reverse(
            'api:store:track-upload-initiate',
            args=(album.pk,),
        )

        response = artist_client.post(
            url,
            data={
                'filename': 'cover.jpg',
                'size': 123,
                'content_type': 'image/jpeg',
                'name': 'Invalid',
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
        """Создаёт трек, загружает local staging и завершает upload."""
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

        album = AlbumFactory(artist=artist_user.artist_profile)
        file_content = b'test audio content'

        initiate_url = reverse(
            'api:store:track-upload-initiate',
            args=(album.pk,),
        )

        initiate_response = artist_client.post(
            initiate_url,
            data={
                'filename': '01 Intro.flac',
                'size': len(file_content),
                'content_type': 'audio/flac',
                'name': 'Intro',
                'description': 'Описание.',
                'price': '100.00',
                'allow_overpay': True,
            },
            format='json',
        )

        assert initiate_response.status_code == HTTPStatus.CREATED

        initiate_data = initiate_response.json()
        track_id = initiate_data['track']['id']
        upload_id = initiate_data['upload']['id']
        transport = initiate_data['upload']['transport']

        assert initiate_data['track']['position'] == 1
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

        assert storage.exists(upload.staging_key)

        complete_url = initiate_data['upload']['complete_url']

        with patch(
            'store.services.track_upload.upload_storage.'
            'TrackGeneratedAudioScheduler.schedule',
        ) as mocked_schedule:
            with patch.object(
                AlbumArchiveScheduler,
                'schedule_by_id',
                return_value=True,
            ) as mocked_archive_schedule:
                with django_capture_on_commit_callbacks(execute=True):
                    complete_response = artist_client.post(complete_url)

        assert complete_response.status_code == HTTPStatus.OK

        complete_data = complete_response.json()

        assert complete_data['track'] == {
            'id': track_id,
            'name': 'Intro',
            'description': 'Описание.',
            'position': 1,
            'price': '100.00',
            'allow_overpay': True,
            'isrc': None,
        }
        assert complete_data['upload']['id'] == upload_id
        assert complete_data['upload']['status'] == (
            TrackUpload.Status.COMPLETED
        )
        assert complete_data['upload']['uploaded_size'] == len(file_content)
        assert complete_data['upload']['completed_at'] is not None

        release_track = ReleaseTrack.objects.select_related(
            'recording',
        ).get(pk=track_id)
        recording = release_track.recording
        upload.refresh_from_db()

        assert upload.track == recording
        assert recording.audio_file
        assert release_track.position == 1
        assert recording.audio_file.name.startswith(
            'recordings/original/',
        )
        assert storage.exists(recording.audio_file.name)
        assert not storage.exists(upload.staging_key)

        mocked_schedule.assert_called_once_with(recording)
        mocked_archive_schedule.assert_called_once_with(album.pk)

    def test_cannot_complete_foreign_upload(
        self,
        artist_client,
    ):
        """Не позволяет завершить чужую загрузку трека."""
        release_track = ReleaseTrackFactory()
        upload = TrackUpload.objects.create(
            track=release_track.recording,
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

        response = artist_client.post(
            f'{url}?track_id={release_track.pk}',
        )

        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_rejects_complete_for_unrelated_release_track(
        self,
        artist_client,
        artist_user,
    ):
        """Не принимает внешний track из другой Recording."""
        album = AlbumFactory(artist=artist_user.artist_profile)
        release_track = ReleaseTrackFactory(release=album)
        unrelated_track = ReleaseTrackFactory(release=album)
        upload = TrackUpload.objects.create(
            track=release_track.recording,
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

        response = artist_client.post(
            f'{url}?track_id={unrelated_track.pk}',
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        upload.refresh_from_db()
        assert upload.status == TrackUpload.Status.INITIATED

    @patch(
        'store.views.track_upload.'
        'TrackUploadTransportService.create_instruction',
    )
    def test_initiates_track_file_replacement_upload(
        self,
        mocked_create_instruction,
        artist_client,
        artist_user,
    ):
        """Создаёт попытку замены файла существующего трека."""
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
            'api:store:track-file-upload-initiate',
            args=(release_track.pk,),
        )

        response = artist_client.post(
            url,
            data={
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

        assert data['track']['id'] == release_track.pk
        assert data['track']['name'] == release_track.name
        assert data['track']['position'] == 5
        assert data['upload']['complete_url'].endswith(
            f'?track_id={release_track.pk}',
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

        mocked_create_instruction.assert_called_once()

    def test_rejects_track_file_replacement_for_foreign_track(
        self,
        artist_client,
    ):
        """Не позволяет артисту заменить файл чужого трека."""
        release_track = ReleaseTrackFactory()

        url = reverse(
            'api:store:track-file-upload-initiate',
            args=(release_track.pk,),
        )

        response = artist_client.post(
            url,
            data={
                'filename': 'new-original.flac',
                'size': 123,
                'content_type': 'audio/flac',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert TrackUpload.objects.count() == 0
