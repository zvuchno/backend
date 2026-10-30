"""Тесты завершения загрузки оригинальных файлов треков."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import call, patch

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from store.models import (
    AlbumArchive,
    Product,
    Recording,
    ReleaseTrack,
    TrackUpload,
)
from store.services import ProductService
from store.services.album_archive import AlbumArchiveScheduler
from store.services.track_upload import (
    TrackUploadCleanupService,
    TrackUploadService,
    TrackUploadStorageError,
    TrackUploadStorageService,
)
from store.tests.factories import (
    AlbumFactory,
    ReleaseTrackFactory,
    make_audio_file,
)


@pytest.mark.django_db
class TestTrackUploadStorageService:
    """Тесты переноса staging-файлов в постоянное хранилище."""

    def test_completes_local_upload_and_removes_staging_file(
        self,
        artist_user,
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
        audio_file_field = Recording._meta.get_field('audio_file')

        monkeypatch.setattr(
            audio_file_field,
            'storage',
            storage,
        )

        file_content = b'test audio content'

        recording, upload = TrackUploadService.create_recording_upload(
            owner=artist_user.artist_profile,
            created_by=artist_user,
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
        ) as mocked_schedule:
            with patch.object(
                AlbumArchiveScheduler,
                'schedule_by_id',
                return_value=True,
            ) as mocked_archive_schedule:
                with django_capture_on_commit_callbacks(execute=True):
                    completed_upload = TrackUploadStorageService.complete(
                        upload=received_upload,
                    )

        recording.refresh_from_db()
        completed_upload.refresh_from_db()

        assert completed_upload.status == TrackUpload.Status.COMPLETED
        assert completed_upload.uploaded_size == len(file_content)
        assert completed_upload.completed_at is not None
        assert completed_upload.error == ''

        assert recording.audio_file.name
        assert recording.audio_file.name.startswith('recordings/original/')
        assert recording.audio_file.name.endswith('.flac')

        assert storage.exists(recording.audio_file.name)
        assert not storage.exists(upload.staging_key)

        with storage.open(recording.audio_file.name, 'rb') as audio_file:
            assert audio_file.read() == file_content

        mocked_schedule.assert_called_once_with(recording)
        mocked_archive_schedule.assert_not_called()

    def test_raises_error_when_local_staging_file_is_missing(
        self,
        artist_user,
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
        audio_file_field = Recording._meta.get_field('audio_file')

        monkeypatch.setattr(
            audio_file_field,
            'storage',
            storage,
        )

        recording, upload = TrackUploadService.create_recording_upload(
            owner=artist_user.artist_profile,
            created_by=artist_user,
            filename='missing.flac',
            size=10,
            content_type='audio/flac',
        )

        with pytest.raises(
            TrackUploadStorageError,
            match='Временный файл загрузки не найден',
        ):
            TrackUploadStorageService.complete(
                upload=upload,
            )

        upload.refresh_from_db()
        recording.refresh_from_db()

        assert not recording.audio_file
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
        audio_file_field = Recording._meta.get_field('audio_file')

        monkeypatch.setattr(
            audio_file_field,
            'storage',
            storage,
        )

        album = AlbumFactory()
        release_track = ReleaseTrackFactory(
            release=album,
            position=7,
            recording__audio_file=make_audio_file(
                name='old-original.mp3',
                content=b'old audio content',
            ),
        )
        recording = release_track.recording

        ProductService.ensure_commerce(
            release_track,
            validated_data={
                'price': Decimal('250.00'),
                'allow_overpay': True,
                'variants': [],
            },
        )

        old_release_track_id = release_track.pk
        old_recording_id = recording.pk
        old_position = release_track.position
        old_audio_name = recording.audio_file.name
        old_product_id = release_track.product.id

        new_content = b'new audio content'

        upload = TrackUploadService.create_replacement_upload(
            recording=recording,
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
                'schedule_by_id',
                return_value=True,
            ) as mocked_archive_schedule:
                with django_capture_on_commit_callbacks(execute=True):
                    completed_upload = TrackUploadStorageService.complete(
                        upload=received_upload,
                    )

        release_track.refresh_from_db()
        recording.refresh_from_db()
        completed_upload.refresh_from_db()

        assert completed_upload.status == TrackUpload.Status.COMPLETED
        assert completed_upload.uploaded_size == len(new_content)
        assert completed_upload.completed_at is not None
        assert completed_upload.error == ''

        assert release_track.pk == old_release_track_id
        assert recording.pk == old_recording_id
        assert release_track.position == old_position
        assert release_track.product.id == old_product_id
        assert release_track.product.price == Decimal('250.00')
        assert release_track.product.allow_overpay is True

        assert recording.audio_file.name != old_audio_name
        assert recording.audio_file.name.startswith('recordings/original/')
        assert recording.audio_file.name.endswith('.flac')

        assert storage.exists(recording.audio_file.name)
        assert storage.exists(old_audio_name)
        assert not storage.exists(upload.staging_key)

        with storage.open(recording.audio_file.name, 'rb') as audio_file:
            assert audio_file.read() == new_content

        mocked_audio_schedule.assert_called_once_with(recording)
        mocked_archive_schedule.assert_called_once_with(album.pk)

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
        audio_file_field = Recording._meta.get_field('audio_file')

        monkeypatch.setattr(
            audio_file_field,
            'storage',
            storage,
        )

        release_track = ReleaseTrackFactory(
            recording__audio_file=make_audio_file(
                name='old-original.mp3',
                content=b'old audio content',
            ),
        )
        recording = release_track.recording

        old_audio_name = recording.audio_file.name

        upload = TrackUploadService.create_replacement_upload(
            recording=recording,
            filename='missing-new-original.flac',
            size=10,
            content_type='audio/flac',
        )

        with pytest.raises(
            TrackUploadStorageError,
            match='Временный файл загрузки не найден',
        ):
            TrackUploadStorageService.complete(
                upload=upload,
            )

        recording.refresh_from_db()
        upload.refresh_from_db()

        assert recording.audio_file.name == old_audio_name
        assert storage.exists(old_audio_name)

        assert upload.status == TrackUpload.Status.INITIATED
        assert upload.completed_at is None

    def test_complete_is_idempotent_for_completed_upload(
        self,
        artist_user,
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
        audio_file_field = Recording._meta.get_field('audio_file')

        monkeypatch.setattr(
            audio_file_field,
            'storage',
            storage,
        )

        file_content = b'test audio content'

        recording, upload = TrackUploadService.create_recording_upload(
            owner=artist_user.artist_profile,
            created_by=artist_user,
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
                'schedule_by_id',
                return_value=True,
            ) as mocked_archive_schedule:
                with django_capture_on_commit_callbacks(execute=True):
                    completed_upload = TrackUploadStorageService.complete(
                        upload=upload,
                    )

                recording.refresh_from_db()
                first_audio_file_name = recording.audio_file.name

                second_completed_upload = TrackUploadStorageService.complete(
                    upload=completed_upload,
                )

        recording.refresh_from_db()
        second_completed_upload.refresh_from_db()

        assert second_completed_upload.status == TrackUpload.Status.COMPLETED
        assert recording.audio_file.name == first_audio_file_name
        assert not storage.exists(upload.staging_key)

        assert mocked_audio_schedule.call_count == 1
        assert mocked_archive_schedule.call_count == 0

    def test_schedules_archives_for_every_release_using_recording(
        self,
        settings,
        tmp_path,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Замена общего оригинала обновляет архивы всех связанных релизов."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Recording._meta.get_field('audio_file')
        monkeypatch.setattr(audio_file_field, 'storage', storage)

        # 1. Создаём независимую запись и upload.
        first_album = AlbumFactory()
        original_content = b'shared audio content'

        recording, create_upload = TrackUploadService.create_recording_upload(
            owner=first_album.artist,
            created_by=first_album.created_by,
            filename='shared.flac',
            size=len(original_content),
            content_type='audio/flac',
        )

        create_upload = TrackUploadService.receive_local_file(
            upload=create_upload,
            uploaded_file=SimpleUploadedFile(
                name='shared.flac',
                content=original_content,
                content_type='audio/flac',
            ),
        )

        # 2. Полностью завершаем первоначальный CREATE.
        # Планировщики здесь мокируем: в этом тесте
        # нас интересует последующая замена оригинала.
        with (
            patch(
                'store.services.track_upload.upload_storage.'
                'TrackGeneratedAudioScheduler.schedule',
            ),
            patch.object(
                AlbumArchiveScheduler,
                'schedule_by_id',
                return_value=True,
            ),
            django_capture_on_commit_callbacks(execute=True),
        ):
            TrackUploadStorageService.complete(
                upload=create_upload,
            )

        recording.refresh_from_db()
        assert recording.audio_file

        # 3. Размещаем уже загруженную запись в двух релизах.
        release_track = ReleaseTrackFactory(
            release=first_album,
            recording=recording,
        )
        second_album = AlbumFactory(artist=first_album.artist)

        second_release_track = ReleaseTrackFactory(
            release=second_album,
            recording=recording,
        )
        initial_positions = (
            release_track.position,
            second_release_track.position,
        )

        assert second_release_track.recording_id == recording.pk

        # 4. Начинаем замену общего оригинального файла.
        new_content = b'updated shared audio content'

        replace_upload = TrackUploadService.create_replacement_upload(
            recording=recording,
            filename='shared-new.flac',
            size=len(new_content),
            content_type='audio/flac',
        )

        replace_upload = TrackUploadService.receive_local_file(
            upload=replace_upload,
            uploaded_file=SimpleUploadedFile(
                name='shared-new.flac',
                content=new_content,
                content_type='audio/flac',
            ),
        )

        # 5. Завершаем REPLACE и проверяем планировщики.
        with (
            patch(
                'store.services.track_upload.upload_storage.'
                'TrackGeneratedAudioScheduler.schedule',
            ) as mocked_audio_schedule,
            patch.object(
                AlbumArchiveScheduler,
                'schedule_by_id',
                return_value=True,
            ) as mocked_archive_schedule,
            django_capture_on_commit_callbacks(execute=True),
        ):
            completed_upload = TrackUploadStorageService.complete(
                upload=replace_upload,
            )

        assert completed_upload.status == TrackUpload.Status.COMPLETED

        mocked_audio_schedule.assert_called_once_with(recording)

        assert mocked_archive_schedule.call_count == 2
        mocked_archive_schedule.assert_has_calls(
            [
                call(first_album.pk),
                call(second_album.pk),
            ],
            any_order=True,
        )

        # 6. Замена файла не должна менять размещения.
        release_track.refresh_from_db()
        second_release_track.refresh_from_db()

        assert release_track.is_active is True
        assert (
            release_track.position,
            second_release_track.position,
        ) == initial_positions
        assert second_release_track.recording_id == recording.pk

    def test_archive_enqueue_failure_does_not_block_callbacks_and_retry(
        self,
        settings,
        tmp_path,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Ошибка первой ZIP-задачи не мешает остальным callbacks и retry."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Recording._meta.get_field('audio_file')
        monkeypatch.setattr(audio_file_field, 'storage', storage)

        first_album = AlbumFactory()
        second_album = AlbumFactory(artist=first_album.artist)
        file_content = b'shared original content'
        recording, upload = TrackUploadService.create_recording_upload(
            owner=first_album.artist,
            created_by=first_album.created_by,
            filename='shared.flac',
            size=len(file_content),
            content_type='audio/flac',
        )
        ReleaseTrackFactory(release=first_album, recording=recording)
        ReleaseTrackFactory(release=second_album, recording=recording)
        upload = TrackUploadService.receive_local_file(
            upload=upload,
            uploaded_file=SimpleUploadedFile(
                name='shared.flac',
                content=file_content,
                content_type='audio/flac',
            ),
        )

        with (
            patch(
                'store.services.track_upload.upload_storage.'
                'TrackGeneratedAudioScheduler.schedule',
            ),
            patch.object(
                AlbumArchiveScheduler,
                'schedule_by_id',
                wraps=AlbumArchiveScheduler.schedule_by_id,
            ) as mocked_archive_schedule,
            patch(
                'store.tasks.album_archive.build_album_archive.apply_async',
                side_effect=(RuntimeError('Broker unavailable'), None),
            ) as mocked_archive_enqueue,
            patch.object(
                TrackUploadStorageService,
                '_delete_staging_safely',
                wraps=TrackUploadStorageService._delete_staging_safely,
            ) as mocked_staging_cleanup,
        ):
            with django_capture_on_commit_callbacks(execute=True):
                completed_upload = TrackUploadStorageService.complete(
                    upload=upload,
                )

            recording.refresh_from_db()
            completed_upload.refresh_from_db()

            assert recording.audio_file
            assert storage.exists(recording.audio_file.name)
            assert completed_upload.status == TrackUpload.Status.COMPLETED
            assert completed_upload.completed_at is not None
            assert mocked_archive_schedule.call_count == 2
            mocked_archive_schedule.assert_has_calls(
                [
                    call(first_album.pk),
                    call(second_album.pk),
                ],
                any_order=True,
            )
            assert mocked_archive_enqueue.call_count == 2
            failed_album_id = mocked_archive_enqueue.call_args_list[0].kwargs[
                'args'
            ][0]
            successful_album_id = mocked_archive_enqueue.call_args_list[
                1
            ].kwargs['args'][0]
            assert {failed_album_id, successful_album_id} == {
                first_album.pk,
                second_album.pk,
            }
            mocked_staging_cleanup.assert_called_once()
            assert not storage.exists(upload.staging_key)

            failed_archive = AlbumArchive.objects.get(
                album_id=failed_album_id,
            )
            successful_archive = AlbumArchive.objects.get(
                album_id=successful_album_id,
            )
            failed_hash = failed_archive.pending_hash

            assert failed_archive.status == AlbumArchive.Status.FAILED
            assert failed_hash
            assert failed_archive.error_message == 'Broker unavailable'
            assert successful_archive.status == AlbumArchive.Status.PENDING
            assert successful_archive.pending_hash

            mocked_archive_enqueue.reset_mock()
            mocked_archive_enqueue.side_effect = None

            with django_capture_on_commit_callbacks(execute=True) as callbacks:
                retry_results = [
                    AlbumArchiveScheduler.schedule_by_id(failed_album_id),
                    AlbumArchiveScheduler.schedule_by_id(successful_album_id),
                ]

            assert retry_results == [True, False]
            assert len(callbacks) == 1
            mocked_archive_enqueue.assert_called_once_with(
                args=(failed_album_id, failed_hash),
                countdown=AlbumArchiveScheduler.REBUILD_DELAY_SECONDS,
            )

            failed_archive.refresh_from_db()
            successful_archive.refresh_from_db()

            assert failed_archive.status == AlbumArchive.Status.PENDING
            assert failed_archive.pending_hash == failed_hash
            assert failed_archive.error_message == ''
            assert successful_archive.status == AlbumArchive.Status.PENDING

    def test_staging_delete_failure_is_retried_by_cleanup(
        self,
        settings,
        tmp_path,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Cleanup повторяет удаление staging завершённой загрузки."""
        settings.USE_S3_MEDIA = False

        storage = FileSystemStorage(
            location=tmp_path,
            base_url='/private/',
        )
        audio_file_field = Recording._meta.get_field('audio_file')
        monkeypatch.setattr(audio_file_field, 'storage', storage)

        album = AlbumFactory()
        release_track = ReleaseTrackFactory(
            release=album,
            position=7,
            recording__audio_file=make_audio_file(
                name='old-original.mp3',
                content=b'old audio content',
            ),
        )
        recording = release_track.recording
        product = ProductService.ensure_commerce(
            release_track,
            validated_data={
                'price': Decimal('250.00'),
                'allow_overpay': True,
                'variants': [],
            },
        )
        release_track_id = release_track.pk
        product_id = product.pk
        position = release_track.position

        file_content = b'new original content'
        upload = TrackUploadService.create_replacement_upload(
            recording=recording,
            filename='new-original.flac',
            size=len(file_content),
            content_type='audio/flac',
        )
        upload = TrackUploadService.receive_local_file(
            upload=upload,
            uploaded_file=SimpleUploadedFile(
                name='new-original.flac',
                content=file_content,
                content_type='audio/flac',
            ),
        )

        with (
            patch(
                'store.services.track_upload.upload_storage.'
                'TrackGeneratedAudioScheduler.schedule',
            ),
            patch.object(
                AlbumArchiveScheduler,
                'schedule_by_id',
                return_value=True,
            ),
            patch.object(
                TrackUploadStorageService,
                'delete_staging',
                side_effect=RuntimeError('Storage unavailable'),
            ) as mocked_staging_delete,
            django_capture_on_commit_callbacks(execute=True),
        ):
            completed_upload = TrackUploadStorageService.complete(
                upload=upload,
            )

        recording.refresh_from_db()
        completed_upload.refresh_from_db()
        release_track.refresh_from_db()
        product.refresh_from_db()

        assert mocked_staging_delete.call_count == 1
        assert recording.audio_file
        assert storage.exists(recording.audio_file.name)
        with storage.open(recording.audio_file.name, 'rb') as audio_file:
            assert audio_file.read() == file_content
        assert completed_upload.status == TrackUpload.Status.COMPLETED
        assert completed_upload.completed_at is not None
        assert storage.exists(upload.staging_key)

        assert ReleaseTrack.objects.filter(pk=release_track_id).exists()
        assert release_track.position == position
        assert release_track.recording_id == recording.pk
        assert Product.objects.filter(pk=product_id).exists()
        assert product.track_id == release_track.pk
        assert product.price == Decimal('250.00')
        assert product.allow_overpay is True

        audio_file_name = recording.audio_file.name
        TrackUpload.objects.filter(pk=upload.pk).update(
            completed_at=timezone.now() - timedelta(hours=23),
        )
        completed_upload.refresh_from_db()

        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            repeated_upload = TrackUploadStorageService.complete(
                upload=completed_upload,
            )

        recording.refresh_from_db()

        assert not callbacks
        assert repeated_upload.pk == completed_upload.pk
        assert repeated_upload.status == TrackUpload.Status.COMPLETED
        assert recording.audio_file.name == audio_file_name
        assert storage.exists(recording.audio_file.name)
        assert storage.exists(upload.staging_key)

        recent_cleanup_result = TrackUploadCleanupService.cleanup_expired()

        assert recent_cleanup_result == {
            'deleted': 0,
            'skipped': 0,
            'storage_errors': 0,
        }
        assert TrackUpload.objects.filter(pk=upload.pk).exists()
        assert storage.exists(upload.staging_key)

        TrackUpload.objects.filter(pk=upload.pk).update(
            completed_at=timezone.now() - timedelta(days=2),
        )

        with patch(
            'store.services.track_upload.clean_up.'
            'TrackUploadStorageService.delete_staging',
            side_effect=RuntimeError('Storage unavailable'),
        ):
            failed_cleanup_result = TrackUploadCleanupService.cleanup_expired()

        assert failed_cleanup_result == {
            'deleted': 0,
            'skipped': 0,
            'storage_errors': 1,
        }
        assert TrackUpload.objects.filter(pk=upload.pk).exists()
        assert storage.exists(upload.staging_key)

        recovered_cleanup_result = TrackUploadCleanupService.cleanup_expired()

        assert recovered_cleanup_result == {
            'deleted': 1,
            'skipped': 0,
            'storage_errors': 0,
        }
        assert not TrackUpload.objects.filter(pk=upload.pk).exists()
        assert not storage.exists(upload.staging_key)

        repeated_cleanup_result = TrackUploadCleanupService.cleanup_expired()

        assert repeated_cleanup_result == {
            'deleted': 0,
            'skipped': 0,
            'storage_errors': 0,
        }

        recording.refresh_from_db()
        release_track.refresh_from_db()
        product.refresh_from_db()

        assert recording.audio_file.name == audio_file_name
        assert storage.exists(recording.audio_file.name)
        assert ReleaseTrack.objects.filter(pk=release_track_id).exists()
        assert release_track.recording_id == recording.pk
        assert release_track.position == position
        assert Product.objects.filter(pk=product_id).exists()
        assert product.track_id == release_track.pk
        assert product.price == Decimal('250.00')
        assert product.allow_overpay is True
