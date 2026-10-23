import hashlib
import subprocess
from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile

from store.admin.track import RecordingAdmin
from store.exceptions import TemporaryAudioStorageError
from store.models import Recording, TrackGeneratedAudio
from store.services.audio import (
    AudioProcessingService,
    TrackAudioPreparationService,
    TrackGeneratedAudioScheduler,
    calculate_file_hash,
)
from store.services.audio.processing import AudioMetadata
from store.services.track_upload import TrackUploadStorageService
from store.tasks.audio import prepare_track_audio
from store.tests.factories import RecordingFactory, make_audio_file

pytestmark = pytest.mark.django_db


def test_calculate_file_hash_returns_content_sha256():
    """Возвращает SHA-256 содержимого открытого файла."""
    content = b'original audio bytes'

    result = calculate_file_hash(BytesIO(content))

    assert result == hashlib.sha256(content).hexdigest()


def test_prepare_updates_recording_duration_and_hash():
    """Подготовка работает с Recording и сохраняет метаданные original."""
    content = b'recording original content'
    recording = RecordingFactory(
        audio_file=make_audio_file(
            name='original.flac',
            content=content,
        ),
    )

    with (
        patch.object(
            AudioProcessingService,
            'probe_metadata',
            return_value=AudioMetadata(duration=137),
        ),
        patch.object(TrackAudioPreparationService, '_prepare_stream'),
        patch.object(TrackAudioPreparationService, '_prepare_preview'),
    ):
        TrackAudioPreparationService.prepare(recording.pk)

    recording.refresh_from_db()
    generated = TrackGeneratedAudio.objects.get(track=recording)

    assert generated.track == recording
    assert recording.duration == 137
    assert recording.file_hash == hashlib.sha256(content).hexdigest()


def test_download_source_file_hashes_the_same_chunks_it_writes(tmp_path):
    """Original скачивается и хешируется за один проход по потоку."""
    chunks = (b'first chunk', b'second chunk', b'third chunk')

    class ChunkedSource:
        def __init__(self):
            self.chunks = iter((*chunks, b''))
            self.read_calls = 0

        def read(self, _size) -> bytes:
            self.read_calls += 1
            return next(self.chunks)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class AudioFile:
        name = 'recordings/original/source.flac'

        def __init__(self):
            self.open_calls = 0
            self.source = ChunkedSource()

        def open(self, mode) -> ChunkedSource:
            assert mode == 'rb'
            self.open_calls += 1
            return self.source

    audio_file = AudioFile()
    recording = Mock(pk=101, audio_file=audio_file)

    source_path, file_hash = (
        TrackAudioPreparationService._download_source_file(
            recording=recording,
            workdir=tmp_path,
        )
    )

    content = b''.join(chunks)
    assert source_path.read_bytes() == content
    assert file_hash == hashlib.sha256(content).hexdigest()
    assert audio_file.open_calls == 1
    assert audio_file.source.read_calls == len(chunks) + 1


def test_download_source_file_converts_temporary_storage_error(tmp_path):
    """Временная ошибка чтения original остаётся retryable."""
    audio_file = Mock()
    audio_file.name = 'recordings/original/source.flac'
    audio_file.open.side_effect = TimeoutError('Storage timeout')
    recording = Mock(pk=101, audio_file=audio_file)

    with pytest.raises(TemporaryAudioStorageError):
        TrackAudioPreparationService._download_source_file(
            recording=recording,
            workdir=tmp_path,
        )


def test_preview_failure_does_not_mark_stream_as_failed(tmp_path):
    """Ошибка preview не переносится в состояние stream."""
    recording = RecordingFactory()
    generated = TrackGeneratedAudio.objects.create(
        track=recording,
        stream_status=TrackGeneratedAudio.ProcessingStatus.READY,
        stream_error='',
    )

    with (
        patch.object(
            AudioProcessingService,
            'create_preview',
            side_effect=ValueError('preview failed'),
        ),
        pytest.raises(ValueError, match='preview failed'),
    ):
        TrackAudioPreparationService._prepare_preview(
            generated=generated,
            source_path=tmp_path / 'source.flac',
            target_path=tmp_path / 'preview.mp3',
            source_duration=120,
        )

    generated.refresh_from_db()
    assert generated.preview_status == (
        TrackGeneratedAudio.ProcessingStatus.FAILED
    )
    assert generated.preview_error == 'preview failed'
    assert generated.stream_status == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )
    assert generated.stream_error == ''


def test_stream_failure_does_not_mark_preview_as_failed(tmp_path):
    """Ошибка stream не переносится в состояние preview."""
    recording = RecordingFactory()
    generated = TrackGeneratedAudio.objects.create(
        track=recording,
        preview_status=TrackGeneratedAudio.ProcessingStatus.READY,
        preview_error='',
    )

    with (
        patch.object(
            AudioProcessingService,
            'create_stream',
            side_effect=ValueError('stream failed'),
        ),
        pytest.raises(ValueError, match='stream failed'),
    ):
        TrackAudioPreparationService._prepare_stream(
            generated=generated,
            source_path=tmp_path / 'source.flac',
            target_path=tmp_path / 'stream.mp3',
        )

    generated.refresh_from_db()
    assert generated.stream_status == (
        TrackGeneratedAudio.ProcessingStatus.FAILED
    )
    assert generated.stream_error == 'stream failed'
    assert generated.preview_status == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )
    assert generated.preview_error == ''


def test_scheduler_enqueues_recording_id_after_commit(
    django_capture_on_commit_callbacks,
):
    """Scheduler после commit передаёт задаче id Recording."""
    recording = RecordingFactory()

    with patch(
        'store.tasks.audio.prepare_track_audio.delay',
    ) as delay_mock:
        with django_capture_on_commit_callbacks(execute=True):
            TrackGeneratedAudioScheduler.schedule(recording)

    delay_mock.assert_called_once_with(recording.pk)


def test_prepare_task_passes_recording_id():
    """Celery task передаёт сервису id Recording."""
    recording = RecordingFactory()

    with patch.object(
        TrackAudioPreparationService,
        'prepare',
    ) as prepare_mock:
        prepare_track_audio.run(recording.pk)

    prepare_mock.assert_called_once_with(recording.pk)


def test_prepare_task_retries_temporary_storage_error():
    """Celery task сохраняет retry для временной ошибки storage."""
    error = TemporaryAudioStorageError('Storage timeout')

    with (
        patch.object(
            TrackAudioPreparationService,
            'prepare',
            side_effect=error,
        ),
        patch.object(
            prepare_track_audio,
            'retry',
            side_effect=RuntimeError('retry requested'),
        ) as retry_mock,
        pytest.raises(RuntimeError, match='retry requested'),
    ):
        prepare_track_audio.run(123)

    retry_mock.assert_called_once_with(exc=error)


def test_direct_upload_audio_replacement_clears_file_hash():
    """Назначение нового original через direct upload сбрасывает hash."""
    recording = RecordingFactory(file_hash='old-hash')

    TrackUploadStorageService._set_recording_audio(
        recording=recording,
        final_key='recordings/original/replacement.flac',
    )

    recording.refresh_from_db()
    assert recording.audio_file.name == (
        'recordings/original/replacement.flac'
    )
    assert recording.file_hash == ''


def test_recording_admin_audio_replacement_clears_file_hash(
    django_capture_on_commit_callbacks,
):
    """RecordingAdmin сбрасывает hash при замене original."""
    recording = RecordingFactory(file_hash='old-hash')
    form = Mock(changed_data=['audio_file'])
    model_admin = RecordingAdmin(Recording, AdminSite())

    with patch.object(
        TrackGeneratedAudioScheduler,
        'schedule',
    ) as schedule_mock:
        with django_capture_on_commit_callbacks(execute=True):
            model_admin.save_model(
                request=Mock(),
                obj=recording,
                form=form,
                change=True,
            )

    recording.refresh_from_db()
    assert recording.file_hash == ''
    schedule_mock.assert_called_once_with(recording)


def test_recording_admin_metadata_update_keeps_file_hash():
    """RecordingAdmin не сбрасывает hash при изменении метаданных."""
    recording = RecordingFactory(file_hash='existing-hash')
    form = Mock(changed_data=['name'])
    model_admin = RecordingAdmin(Recording, AdminSite())

    with patch.object(
        TrackGeneratedAudioScheduler,
        'schedule',
    ) as schedule_mock:
        model_admin.save_model(
            request=Mock(),
            obj=recording,
            form=form,
            change=True,
        )

    recording.refresh_from_db()
    assert recording.file_hash == 'existing-hash'
    schedule_mock.assert_not_called()


def test_equal_file_hashes_do_not_merge_recordings():
    """Совпадающий SHA-256 не дедуплицирует мастер-записи."""
    first = RecordingFactory(file_hash='same-hash')
    second = RecordingFactory(file_hash='same-hash')

    assert first.pk != second.pk
    assert Recording.objects.filter(file_hash='same-hash').count() == 2


@patch('store.services.audio.processing.subprocess.run')
def test_create_preview_uses_intro_and_remaining_middle(
    run_mock,
    tmp_path,
):
    """Для длинного трека preview собирается из начала и второй части."""
    run_mock.return_value = subprocess.CompletedProcess(
        args=(),
        returncode=0,
        stdout='',
        stderr='',
    )

    source_path = tmp_path / 'source.flac'
    target_path = tmp_path / 'preview.mp3'

    AudioProcessingService.create_preview(
        source_path=source_path,
        target_path=target_path,
        source_duration=120,
    )

    command = run_mock.call_args.args[0]

    assert '-filter_complex' in command

    filter_complex = command[command.index('-filter_complex') + 1]

    assert 'atrim=start=0:duration=15' in filter_complex
    assert 'atrim=start=60.0:duration=15' in filter_complex
    assert 'acrossfade=d=1' in filter_complex


def test_replacing_stream_deletes_old_file_after_commit(
    tmp_path,
    django_capture_on_commit_callbacks,
):
    """После успешной замены stream удаляется прежний объект storage."""
    recording = RecordingFactory()
    generated = TrackGeneratedAudio.objects.create(
        track=recording,
        stream_file=SimpleUploadedFile(
            'old-stream.mp3',
            b'old stream',
            content_type='audio/mpeg',
        ),
        stream_status=TrackGeneratedAudio.ProcessingStatus.READY,
    )

    old_name = generated.stream_file.name
    storage = generated.stream_file.storage

    target_path = tmp_path / 'stream.mp3'
    target_path.write_bytes(b'new stream')

    generated.stream_status = TrackGeneratedAudio.ProcessingStatus.READY
    generated.stream_error = ''

    with patch.object(storage, 'delete') as delete_mock:
        with django_capture_on_commit_callbacks(execute=True):
            TrackAudioPreparationService._save_generated_file(
                generated=generated,
                field_name='stream_file',
                target_path=target_path,
                target_filename='stream.mp3',
                update_fields=(
                    'stream_file',
                    'stream_status',
                    'stream_error',
                ),
            )

    generated.refresh_from_db()

    assert generated.stream_file.name != old_name
    delete_mock.assert_called_once_with(old_name)


def test_failed_stream_upload_keeps_old_file(
    tmp_path,
):
    """Ошибка сохранения нового stream не удаляет предыдущий файл."""
    recording = RecordingFactory()
    generated = TrackGeneratedAudio.objects.create(
        track=recording,
        stream_file=SimpleUploadedFile(
            'old-stream.mp3',
            b'old stream',
            content_type='audio/mpeg',
        ),
        stream_status=TrackGeneratedAudio.ProcessingStatus.READY,
    )

    old_name = generated.stream_file.name
    storage = generated.stream_file.storage

    target_path = tmp_path / 'stream.mp3'
    target_path.write_bytes(b'new stream')

    with (
        patch.object(
            storage,
            'save',
            side_effect=OSError('Storage unavailable'),
        ),
        patch.object(storage, 'delete') as delete_mock,
        pytest.raises(OSError),
    ):
        TrackAudioPreparationService._save_generated_file(
            generated=generated,
            field_name='stream_file',
            target_path=target_path,
            target_filename='stream.mp3',
            update_fields=(
                'stream_file',
                'stream_status',
                'stream_error',
            ),
        )

    generated.refresh_from_db()

    assert generated.stream_file.name == old_name
    delete_mock.assert_not_called()
