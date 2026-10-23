"""Тесты внутренних admin endpoint-ов загрузки треков."""

import json
from datetime import timedelta
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
class TestAlbumAdminTrackUpload:
    """Тесты создания черновых треков через Django Admin."""

    @patch(
        'store.admin.album.TrackUploadTransportService.create_instruction',
    )
    def test_creates_pending_track(
        self,
        mocked_create_instruction,
        admin_client,
        staff_user,
    ):
        """Создаёт черновой трек и попытку загрузки."""
        mocked_create_instruction.return_value = UploadInstruction(
            method='POST',
            url='https://storage.test/upload',
            headers={},
            fields={'key': 'value', 'Content-Type': 'audio/flac'},
            file_field_name='file',
            expires_at=timezone.now() + timedelta(hours=1),
        )

        album = AlbumFactory()
        RecordingFactory()

        url = reverse(
            'admin:store_album_track_upload_initiate',
            args=(album.pk,),
        )

        response = admin_client.post(
            url,
            data=json.dumps(
                {
                    'filename': '01 Intro.flac',
                    'size': 10,
                    'content_type': 'audio/flac',
                },
            ),
            content_type='application/json',
        )

        assert response.status_code == HTTPStatus.CREATED

        data = response.json()

        release_track = ReleaseTrack.objects.select_related(
            'recording',
        ).get(pk=data['track']['id'])
        recording = release_track.recording
        upload = TrackUpload.objects.get(pk=data['upload']['id'])

        assert release_track.release == album
        assert release_track.name == '01 Intro'
        assert release_track.position == 1
        assert release_track.is_active is True
        assert recording.created_by == staff_user

        assert upload.track == recording
        assert upload.status == TrackUpload.Status.INITIATED

        assert data['track']['id'] == release_track.pk
        assert data['track']['id'] != recording.pk
        assert data['upload']['id'] == upload.pk
        assert data['track']['name'] == '01 Intro'
        assert data['track']['position'] == 1
        assert data['upload']['status'] == TrackUpload.Status.INITIATED
        complete_path = reverse(
            'admin:store_track_upload_complete',
            args=(upload.pk,),
        )
        assert data['upload']['complete_url'] == (
            f'{complete_path}?track_id={release_track.pk}'
        )
        assert data['upload']['transport'] == {
            'method': 'POST',
            'url': 'https://storage.test/upload',
            'headers': {},
            'fields': {'key': 'value', 'Content-Type': 'audio/flac'},
            'file_field_name': 'file',
        }

        mocked_create_instruction.assert_called_once()
        local_upload_path = reverse(
            'admin:store_track_upload_receive_file',
            args=(upload.pk,),
        )
        assert (
            mocked_create_instruction.call_args.kwargs['local_upload_url']
            == f'{local_upload_path}?track_id={release_track.pk}'
        )

    def test_returns_validation_error_for_invalid_file(self, admin_client):
        """Не создаёт трек для неподдерживаемого файла."""
        album = AlbumFactory()

        url = reverse(
            'admin:store_album_track_upload_initiate',
            args=(album.pk,),
        )

        response = admin_client.post(
            url,
            data=json.dumps(
                {
                    'filename': 'cover.jpg',
                    'size': 10,
                    'content_type': 'image/jpeg',
                },
            ),
            content_type='application/json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert Recording.objects.count() == 0
        assert ReleaseTrack.objects.count() == 0
        assert TrackUpload.objects.count() == 0

    def test_rejects_get_request(self, admin_client):
        """Не принимает GET вместо создания загрузки."""
        album = AlbumFactory()

        url = reverse(
            'admin:store_album_track_upload_initiate',
            args=(album.pk,),
        )

        response = admin_client.get(url)

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_completes_local_upload_flow(
        self,
        admin_client,
        settings,
        tmp_path,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Загружает и завершает файл через внутренние admin endpoint-ы."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Recording._meta.get_field('audio_file')
        monkeypatch.setattr(audio_file_field, 'storage', storage)

        album = AlbumFactory()
        file_content = b'test audio content'

        initiate_url = reverse(
            'admin:store_album_track_upload_initiate',
            args=(album.pk,),
        )

        initiate_response = admin_client.post(
            initiate_url,
            data=json.dumps(
                {
                    'filename': '01 Intro.flac',
                    'size': len(file_content),
                    'content_type': 'audio/flac',
                },
            ),
            content_type='application/json',
        )

        assert initiate_response.status_code == HTTPStatus.CREATED

        initiate_data = initiate_response.json()
        upload_id = initiate_data['upload']['id']
        track_id = initiate_data['track']['id']

        transport = initiate_data['upload']['transport']

        assert transport['method'] == 'POST'
        receive_path = reverse(
            'admin:store_track_upload_receive_file',
            args=(upload_id,),
        )
        assert transport['url'] == f'{receive_path}?track_id={track_id}'
        assert transport['fields'] == {}
        assert transport['file_field_name'] == 'file'

        assert set(transport['headers']) == {
            'X-CSRFToken',
        }
        assert transport['headers']['X-CSRFToken']

        upload_response = admin_client.post(
            transport['url'],
            data={
                'file': SimpleUploadedFile(
                    name='01 Intro.flac',
                    content=file_content,
                    content_type='audio/flac',
                ),
            },
            HTTP_X_CSRFTOKEN=transport['headers']['X-CSRFToken'],
        )

        assert upload_response.status_code == HTTPStatus.OK
        assert upload_response.json()['upload'] == {
            'id': upload_id,
            'status': TrackUpload.Status.UPLOADED,
            'uploaded_size': len(file_content),
        }

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
                    complete_response = admin_client.post(complete_url)

        assert complete_response.status_code == HTTPStatus.OK

        complete_data = complete_response.json()

        assert complete_data['track'] == {
            'id': track_id,
            'name': '01 Intro',
            'position': 1,
            'is_active': True,
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
        upload = TrackUpload.objects.get(pk=upload_id)

        assert upload.track == recording
        assert recording.audio_file
        assert storage.exists(recording.audio_file.name)
        assert release_track.position == 1
        assert upload.status == TrackUpload.Status.COMPLETED
        assert upload.completed_at is not None

        mocked_schedule.assert_called_once_with(recording)
        mocked_archive_schedule.assert_called_once_with(album.pk)

    def test_rejects_release_track_from_another_recording(
        self,
        admin_client,
        settings,
    ):
        """Не принимает чужой ReleaseTrack как контекст upload."""
        settings.USE_S3_MEDIA = False
        album = AlbumFactory()

        initiate_url = reverse(
            'admin:store_album_track_upload_initiate',
            args=(album.pk,),
        )
        initiate_response = admin_client.post(
            initiate_url,
            data=json.dumps(
                {
                    'filename': '01 Intro.flac',
                    'size': 10,
                    'content_type': 'audio/flac',
                },
            ),
            content_type='application/json',
        )
        assert initiate_response.status_code == HTTPStatus.CREATED

        initiate_data = initiate_response.json()
        upload_id = initiate_data['upload']['id']
        release_track = ReleaseTrack.objects.get(
            pk=initiate_data['track']['id'],
        )
        unrelated_track = ReleaseTrackFactory(release=album)

        receive_path = reverse(
            'admin:store_track_upload_receive_file',
            args=(upload_id,),
        )
        receive_response = admin_client.post(
            f'{receive_path}?track_id={unrelated_track.pk}',
            data={
                'file': SimpleUploadedFile(
                    name='01 Intro.flac',
                    content=b'0123456789',
                    content_type='audio/flac',
                ),
            },
        )

        complete_path = reverse(
            'admin:store_track_upload_complete',
            args=(upload_id,),
        )
        complete_response = admin_client.post(
            f'{complete_path}?track_id={unrelated_track.pk}',
        )

        assert receive_response.status_code == HTTPStatus.NOT_FOUND
        assert complete_response.status_code == HTTPStatus.NOT_FOUND
        upload = TrackUpload.objects.get(pk=upload_id)
        assert upload.track == release_track.recording
        assert upload.status == TrackUpload.Status.INITIATED
