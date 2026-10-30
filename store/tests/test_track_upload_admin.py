"""Тесты внутренних admin endpoint-ов загрузки треков."""

import json
from datetime import timedelta
from decimal import Decimal
from http import HTTPStatus
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Permission
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone

from store.models import (
    Album,
    Product,
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
    """Тесты загрузки и размещения записей через Django Admin."""

    @staticmethod
    def initiate(
        client,
        album,
        *,
        filename='01 Intro.flac',
        content=b'audio',
    ) -> HttpResponse:
        """Создаёт мастер-запись и инструкцию загрузки."""
        return client.post(
            reverse(
                'admin:store_album_track_upload_initiate',
                args=(album.pk,),
            ),
            data=json.dumps({
                'filename': filename,
                'size': len(content),
                'content_type': 'audio/flac',
            }),
            content_type='application/json',
        )

    @staticmethod
    def place(client, album, recording) -> HttpResponse:
        """Размещает мастер-запись в альбоме."""
        return client.post(
            reverse(
                'admin:store_album_track_upload_place',
                args=(album.pk,),
            ),
            data=json.dumps({
                'recording_id': recording.pk,
            }),
            content_type='application/json',
        )

    @classmethod
    def upload_and_complete(
        cls,
        client,
        album,
        *,
        filename,
        content,
    ) -> tuple[dict, dict]:
        """Выполняет локальные стадии initiate, upload и complete."""
        initiate_response = cls.initiate(
            client,
            album,
            filename=filename,
            content=content,
        )
        assert initiate_response.status_code == HTTPStatus.CREATED

        initiate_data = initiate_response.json()
        transport = initiate_data['upload']['transport']
        upload_response = client.post(
            transport['url'],
            data={
                'file': SimpleUploadedFile(
                    name=filename,
                    content=content,
                    content_type='audio/flac',
                ),
            },
            HTTP_X_CSRFTOKEN=transport['headers']['X-CSRFToken'],
        )
        assert upload_response.status_code == HTTPStatus.OK

        complete_response = client.post(
            initiate_data['upload']['complete_url'],
        )
        assert complete_response.status_code == HTTPStatus.OK

        return initiate_data, complete_response.json()

    @staticmethod
    def use_local_storage(
        settings,
        monkeypatch,
        tmp_path,
    ) -> FileSystemStorage:
        """Подключает изолированное локальное хранилище записей."""
        settings.USE_S3_MEDIA = False
        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Recording._meta.get_field('audio_file')
        monkeypatch.setattr(audio_file_field, 'storage', storage)
        return storage

    @patch(
        'store.admin.album.TrackUploadTransportService.create_instruction',
    )
    def test_initiate_creates_recording_without_placement(
        self,
        mocked_create_instruction,
        admin_client,
        staff_user,
    ):
        """Initiate создаёт Recording и TrackUpload без ReleaseTrack."""
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

        response = self.initiate(
            admin_client,
            album,
            content=b'0123456789',
        )

        assert response.status_code == HTTPStatus.CREATED

        data = response.json()

        recording = Recording.objects.get(pk=data['recording']['id'])
        upload = TrackUpload.objects.get(pk=data['upload']['id'])

        assert recording.owner == album.artist
        assert recording.name == '01 Intro'
        assert recording.created_by == staff_user
        assert upload.track == recording
        assert upload.status == TrackUpload.Status.INITIATED
        assert not ReleaseTrack.objects.exists()

        assert data['recording'] == {
            'id': recording.pk,
            'name': '01 Intro',
        }
        assert data['upload']['id'] == upload.pk
        assert data['upload']['status'] == TrackUpload.Status.INITIATED
        complete_path = reverse(
            'admin:store_track_upload_complete',
            args=(upload.pk,),
        )
        assert data['upload']['complete_url'] == complete_path
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
            == local_upload_path
        )

    def test_returns_validation_error_for_invalid_file(self, admin_client):
        """Не создаёт трек для неподдерживаемого файла."""
        album = AlbumFactory()

        response = self.initiate(
            admin_client,
            album,
            filename='cover.jpg',
            content=b'0123456789',
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
    ):
        """Локальная загрузка завершается без создания размещения."""
        storage = self.use_local_storage(settings, monkeypatch, tmp_path)

        album = AlbumFactory()
        file_content = b'test audio content'

        with (
            patch(
                'store.services.track_upload.upload_storage.'
                'TrackGeneratedAudioScheduler.schedule',
            ) as mocked_schedule,
            patch.object(
                AlbumArchiveScheduler,
                'schedule_by_id',
            ) as mocked_archive_schedule,
        ):
            initiate_data, complete_data = self.upload_and_complete(
                admin_client,
                album,
                filename='01 Intro.flac',
                content=file_content,
            )

        upload_id = initiate_data['upload']['id']
        recording_id = initiate_data['recording']['id']
        assert complete_data['recording']['id'] == recording_id
        assert complete_data['upload']['id'] == upload_id
        assert complete_data['upload']['status'] == (
            TrackUpload.Status.COMPLETED
        )
        assert complete_data['upload']['uploaded_size'] == len(file_content)
        assert complete_data['upload']['completed_at'] is not None

        recording = Recording.objects.get(pk=recording_id)
        upload = TrackUpload.objects.get(pk=upload_id)

        assert upload.track == recording
        assert recording.audio_file
        assert storage.exists(recording.audio_file.name)
        assert upload.status == TrackUpload.Status.COMPLETED
        assert upload.completed_at is not None
        assert not ReleaseTrack.objects.exists()

        mocked_schedule.assert_called_once_with(recording)
        mocked_archive_schedule.assert_not_called()

    def test_place_creates_zero_price_product(
        self,
        admin_client,
        django_capture_on_commit_callbacks,
    ):
        """Place переиспользует оригинал и создаёт бесплатный Product."""
        album = AlbumFactory(is_published=False)
        recording = RecordingFactory(
            owner=album.artist,
            created_by=album.created_by,
        )
        recording_count = Recording.objects.count()
        original_audio_name = recording.audio_file.name

        with (
            patch.object(
                AlbumArchiveScheduler,
                'schedule_by_id',
            ) as mocked_archive_schedule,
            django_capture_on_commit_callbacks(execute=True),
        ):
            response = self.place(admin_client, album, recording)

        assert response.status_code == HTTPStatus.CREATED
        track = ReleaseTrack.objects.get(
            release=album,
            recording=recording,
        )
        assert track.position == 1
        assert track.is_active is True
        assert track.product.price == Decimal('0.0000')
        assert track.product.allow_overpay is False
        assert Recording.objects.count() == recording_count
        recording.refresh_from_db()
        assert track.recording_id == recording.pk
        assert recording.audio_file.name == original_audio_name
        mocked_archive_schedule.assert_called_once_with(album.pk)

    def test_two_uploaded_files_receive_sequential_positions(
        self,
        admin_client,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """Последовательные загрузки размещаются на соседних позициях."""
        self.use_local_storage(settings, monkeypatch, tmp_path)
        album = AlbumFactory(is_published=False)

        with patch(
            'store.services.track_upload.upload_storage.'
            'TrackGeneratedAudioScheduler.schedule',
        ):
            _, first_complete = self.upload_and_complete(
                admin_client,
                album,
                filename='01 First.flac',
                content=b'first audio',
            )
            first_recording = Recording.objects.get(
                pk=first_complete['recording']['id'],
            )
            first_place = self.place(
                admin_client,
                album,
                first_recording,
            )

            _, second_complete = self.upload_and_complete(
                admin_client,
                album,
                filename='02 Second.flac',
                content=b'second audio',
            )
            second_recording = Recording.objects.get(
                pk=second_complete['recording']['id'],
            )
            second_place = self.place(
                admin_client,
                album,
                second_recording,
            )

        assert first_place.status_code == HTTPStatus.CREATED
        assert second_place.status_code == HTTPStatus.CREATED
        assert list(
            album.tracks.order_by('position').values_list(
                'recording_id',
                'position',
            ),
        ) == [
            (first_recording.pk, 1),
            (second_recording.pk, 2),
        ]

    def test_repeated_complete_and_place_are_idempotent(
        self,
        admin_client,
        settings,
        tmp_path,
        monkeypatch,
    ):
        """Повторы не обрабатывают файл и не меняют товар повторно."""
        self.use_local_storage(settings, monkeypatch, tmp_path)
        album = AlbumFactory(is_published=False)

        with patch(
            'store.services.track_upload.upload_storage.'
            'TrackGeneratedAudioScheduler.schedule',
        ) as mocked_schedule:
            initiate_data, _ = self.upload_and_complete(
                admin_client,
                album,
                filename='Repeat.flac',
                content=b'repeat audio',
            )
            repeated_complete = admin_client.post(
                initiate_data['upload']['complete_url'],
            )

        recording = Recording.objects.get(
            pk=initiate_data['recording']['id'],
        )
        first_place = self.place(admin_client, album, recording)
        track = ReleaseTrack.objects.get(
            release=album,
            recording=recording,
        )
        track.product.price = Decimal('250.0000')
        track.product.allow_overpay = True
        track.product.save(update_fields=('price', 'allow_overpay'))

        product_count = Product.objects.count()
        repeated_place = self.place(admin_client, album, recording)

        assert repeated_complete.status_code == HTTPStatus.OK
        assert mocked_schedule.call_count == 1
        assert first_place.status_code == HTTPStatus.CREATED
        assert repeated_place.status_code == HTTPStatus.OK
        assert repeated_place.json()['created'] is False
        assert (
            ReleaseTrack.objects.filter(
                release=album,
                recording=recording,
            ).count()
            == 1
        )
        assert Product.objects.count() == product_count
        track.product.refresh_from_db()
        assert track.product.price == Decimal('250.0000')
        assert track.product.allow_overpay is True

    def test_superuser_can_place_recording(self, admin_client):
        """Суперпользователь размещает совместимую запись."""
        album = AlbumFactory(is_published=False)
        recording = RecordingFactory(owner=album.artist)

        response = self.place(admin_client, album, recording)

        assert response.status_code == HTTPStatus.CREATED

    def test_staff_without_artist_authority_cannot_place(
        self,
        client,
        user_factory,
    ):
        """Album change permission не даёт staff доступ к чужой записи."""
        staff = user_factory(
            email='album-admin@test.com',
            username='album_admin',
            is_staff=True,
        )
        permission = Permission.objects.get(
            content_type__app_label='store',
            content_type__model='album',
            codename='change_album',
        )
        staff.user_permissions.add(permission)
        client.force_login(staff)
        album = AlbumFactory(is_published=False)
        recording = RecordingFactory(owner=album.artist)

        response = self.place(client, album, recording)

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert not album.tracks.filter(recording=recording).exists()

    def test_rejects_incompatible_recording(
        self,
        admin_client,
    ):
        """Суперпользователь не обходит совместимость профилей."""
        album = AlbumFactory(is_published=False)
        recording = RecordingFactory()
        product_count = Product.objects.count()

        response = self.place(admin_client, album, recording)

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert not album.tracks.filter(recording=recording).exists()
        assert Product.objects.count() == product_count

    def test_places_recording_in_published_album(self, admin_client):
        """Нулевая цена не мешает размещению в опубликованном альбоме."""
        album = AlbumFactory(
            release_type=Album.ReleaseType.ALBUM,
            is_published=True,
        )
        recording = RecordingFactory(owner=album.artist)

        response = self.place(admin_client, album, recording)

        assert response.status_code == HTTPStatus.CREATED
        assert album.tracks.get(recording=recording).product.price == Decimal(
            '0.0000',
        )

    def test_preserves_published_single_track_limit(self, admin_client):
        """В опубликованный сингл нельзя добавить второй активный трек."""
        album = AlbumFactory(
            release_type=Album.ReleaseType.SINGLE,
            is_published=True,
        )
        ReleaseTrackFactory(
            release=album,
            position=1,
            is_active=True,
        )
        recording = RecordingFactory(owner=album.artist)

        response = self.place(admin_client, album, recording)

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert album.tracks.count() == 1
        assert not album.tracks.filter(recording=recording).exists()


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
