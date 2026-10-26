"""Тесты внутренних admin endpoint-ов загрузки треков."""

import json
from datetime import timedelta
from decimal import Decimal
from http import HTTPStatus
from unittest.mock import patch

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from store.models import (
    Recording,
    ReleaseTrack,
    TrackGeneratedAudio,
    TrackUpload,
)
from store.services.album_archive import AlbumArchiveScheduler
from store.services.track_upload import UploadInstruction
from store.tests.factories import (
    AlbumFactory,
    RecordingFactory,
    ReleaseTrackFactory,
)
from store.tests.test_sales_protection import create_order


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
        assert release_track.position is None
        assert release_track.is_active is False
        assert recording.created_by == staff_user

        assert upload.track == recording
        assert upload.status == TrackUpload.Status.INITIATED

        assert data['track']['id'] == release_track.pk
        assert data['track']['id'] != recording.pk
        assert data['upload']['id'] == upload.pk
        assert data['track']['name'] == '01 Intro'
        assert data['track']['position'] is None
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


@pytest.mark.django_db
class TestAlbumAdminTrackInline:
    """HTTP-тесты inline размещений на странице релиза."""

    @staticmethod
    def album_change_data(album, tracks) -> dict:
        """Собирает POST как formset страницы nested_admin."""
        data = {
            'release_type': album.release_type,
            'name': album.name,
            'genre': album.genre_id,
            'release_date': (
                album.release_date.isoformat() if album.release_date else ''
            ),
            'description': album.description,
            'upc': album.upc or '',
            'visibility': album.visibility,
            'product-TOTAL_FORMS': '1',
            'product-INITIAL_FORMS': '0',
            'product-MIN_NUM_FORMS': '0',
            'product-MAX_NUM_FORMS': '1',
            'product-0-price': '0.00',
            'product-0-album': album.pk,
            'archive-TOTAL_FORMS': '0',
            'archive-INITIAL_FORMS': '0',
            'archive-MIN_NUM_FORMS': '0',
            'archive-MAX_NUM_FORMS': '0',
            'bonuses-TOTAL_FORMS': '0',
            'bonuses-INITIAL_FORMS': '0',
            'bonuses-MIN_NUM_FORMS': '0',
            'bonuses-MAX_NUM_FORMS': '1000',
            'tracks-TOTAL_FORMS': str(len(tracks)),
            'tracks-INITIAL_FORMS': str(len(tracks)),
            'tracks-MIN_NUM_FORMS': '0',
            'tracks-MAX_NUM_FORMS': '0',
        }

        if album.is_published:
            data['is_published'] = 'on'
        if album.is_active:
            data['is_active'] = 'on'

        for index, track_data in enumerate(tracks):
            track = track_data['track']
            prefix = f'tracks-{index}'
            data.update({
                f'{prefix}-id': track.pk,
                f'{prefix}-release': album.pk,
                f'{prefix}-position': track_data['position'],
                f'{prefix}-price': track_data['price'],
            })

            if track_data['is_active']:
                data[f'{prefix}-is_active'] = 'on'

        return data

    def test_change_page_shows_existing_release_track(
        self,
        admin_client,
        variant_factory,
    ):
        """Страница релиза показывает данные и аудиостатус трека."""
        variant = variant_factory(
            'track',
            name='Трек в inline',
            price=Decimal('123.45'),
            position=1,
        )
        track = variant.product.track
        track.recording.duration = 187
        track.recording.save(update_fields=('duration',))
        TrackGeneratedAudio.objects.create(
            track=track.recording,
            preview_status=TrackGeneratedAudio.ProcessingStatus.READY,
            stream_status=TrackGeneratedAudio.ProcessingStatus.BUILDING,
        )

        response = admin_client.get(
            reverse(
                'admin:store_album_change',
                args=(track.release_id,),
            ),
        )

        assert response.status_code == HTTPStatus.OK
        assert 'Трек в inline' in response.content.decode()
        assert '187' in response.content.decode()
        assert '123.45' in response.content.decode()
        assert 'Файл не создан' in response.content.decode()
        assert 'Preview:' in response.content.decode()
        assert 'Stream:' in response.content.decode()
        assert 'подготавливается' in response.content.decode()

    def test_change_position_and_price_schedules_archive(
        self,
        admin_client,
        variant_factory,
        django_capture_on_commit_callbacks,
    ):
        """POST inline сохраняет размещение и обновляет архив после commit."""
        variant = variant_factory(
            'track',
            name='Непроданный трек',
            price=Decimal('100.00'),
            position=0,
        )
        track = variant.product.track
        album = track.release
        another_variant = variant_factory(
            'track',
            album=album,
            name='Другой непроданный трек',
            price=Decimal('75.00'),
            position=1,
        )
        another_track = another_variant.product.track
        url = reverse(
            'admin:store_album_change',
            args=(album.pk,),
        )
        data = self.album_change_data(
            album,
            (
                {
                    'track': track,
                    'position': '1',
                    'price': '250.00',
                    'is_active': True,
                },
                {
                    'track': another_track,
                    'position': '0',
                    'price': '75.00',
                    'is_active': True,
                },
            ),
        )
        data['_continue'] = 'Сохранить и продолжить редактирование'

        with (
            patch.object(
                AlbumArchiveScheduler,
                'schedule_by_id',
            ) as mocked_archive_schedule,
            django_capture_on_commit_callbacks(execute=True),
        ):
            response = admin_client.post(url, data=data)
            mocked_archive_schedule.assert_not_called()

        assert response.status_code == HTTPStatus.FOUND

        track.refresh_from_db()
        track.product.refresh_from_db()
        another_track.refresh_from_db()

        assert track.position == 1
        assert another_track.position == 0
        assert track.product.price == Decimal('250.00')
        assert mocked_archive_schedule.called
        assert {
            archive_call.args[0]
            for archive_call in mocked_archive_schedule.call_args_list
        } == {album.pk}

    def test_cannot_deactivate_purchased_release_track(
        self,
        admin_client,
        listener_user,
        variant_factory,
    ):
        """POST inline отклоняет деактивацию купленного трека."""
        variant = variant_factory(
            'track',
            name='Купленный трек',
            price=Decimal('100.00'),
            position=1,
        )
        track = variant.product.track
        album = track.release
        create_order(listener_user, variant)
        url = reverse(
            'admin:store_album_change',
            args=(album.pk,),
        )
        data = self.album_change_data(
            album,
            (
                {
                    'track': track,
                    'position': track.position,
                    'price': '100.00',
                    'is_active': False,
                },
            ),
        )

        response = admin_client.post(url, data=data)

        assert response.status_code == HTTPStatus.OK
        assert (
            'Нельзя деактивировать трек с историей приобретения.'
            in response.content.decode()
        )

        track.refresh_from_db()

        assert track.is_active is True
