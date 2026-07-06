"""Тесты внутренних admin endpoint-ов загрузки треков."""

import json
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from store.models import Track, TrackUpload
from store.services.track_upload import UploadInstruction
from store.tests.factories import AlbumFactory


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

        track = Track.objects.get(pk=data['track']['id'])
        upload = TrackUpload.objects.get(pk=data['upload']['id'])

        assert track.album == album
        assert track.name == '01 Intro'
        assert track.position == 1
        assert track.is_active is False

        assert upload.track == track
        assert upload.status == TrackUpload.Status.INITIATED

        assert data['track']['id'] == track.pk
        assert data['upload']['id'] == upload.pk
        assert data['track']['name'] == '01 Intro'
        assert data['track']['position'] == 1
        assert data['upload']['status'] == TrackUpload.Status.INITIATED
        assert data['upload']['transport'] == {
            'method': 'POST',
            'url': 'https://storage.test/upload',
            'headers': {},
            'fields': {'key': 'value', 'Content-Type': 'audio/flac'},
            'file_field_name': 'file',
        }

        mocked_create_instruction.assert_called_once()

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
        assert Track.objects.count() == 0
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
        django_capture_on_commit_callbacks,
    ):
        """Загружает и завершает файл через внутренние admin endpoint-ы."""
        settings.USE_S3_MEDIA = False

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

        assert transport == {
            'method': 'POST',
            'url': reverse(
                'admin:store_track_upload_receive_file',
                args=(upload_id,),
            ),
            'headers': {},
            'fields': {},
            'file_field_name': 'file',
        }

        upload_response = admin_client.post(
            transport['url'],
            data={
                'file': SimpleUploadedFile(
                    name='01 Intro.flac',
                    content=file_content,
                    content_type='audio/flac',
                ),
            },
        )

        assert upload_response.status_code == HTTPStatus.OK
        assert upload_response.json()['upload'] == {
            'id': upload_id,
            'status': TrackUpload.Status.UPLOADED,
            'uploaded_size': len(file_content),
        }

        complete_url = reverse(
            'admin:store_track_upload_complete',
            args=(upload_id,),
        )

        with patch(
            'store.services.track_upload.upload_storage.'
            'TrackGeneratedAudioScheduler.schedule',
        ) as mocked_schedule:
            with django_capture_on_commit_callbacks(execute=True):
                complete_response = admin_client.post(complete_url)

        assert complete_response.status_code == HTTPStatus.OK

        complete_data = complete_response.json()

        assert complete_data['track'] == {
            'id': track_id,
            'name': '01 Intro',
            'position': 1,
            'is_active': False,
        }

        assert complete_data['upload']['id'] == upload_id
        assert complete_data['upload']['status'] == (
            TrackUpload.Status.COMPLETED
        )
        assert complete_data['upload']['uploaded_size'] == len(file_content)
        assert complete_data['upload']['completed_at'] is not None

        track = Track.objects.get(pk=track_id)
        upload = TrackUpload.objects.get(pk=upload_id)

        assert track.audio_file
        assert upload.status == TrackUpload.Status.COMPLETED
        assert upload.completed_at is not None

        mocked_schedule.assert_called_once_with(track)
