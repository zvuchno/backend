"""Тесты внутренних admin endpoint-ов загрузки треков."""

import json
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

import pytest
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
