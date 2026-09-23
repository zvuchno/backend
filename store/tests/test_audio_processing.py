import subprocess
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from store.exceptions import AudioProcessingError
from store.models import TrackGeneratedAudio
from store.services.audio import (
    AudioProcessingService,
    TrackAudioPreparationService,
)
from store.tests.factories import TrackFactory

pytestmark = pytest.mark.django_db


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
    track = TrackFactory()
    generated = TrackGeneratedAudio.objects.create(
        track=track,
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
    track = TrackFactory()
    generated = TrackGeneratedAudio.objects.create(
        track=track,
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


def test_preview_failure_marks_preview_not_stream_failed(tmp_path):
    """Ошибка preview изменяет только соответствующий статус."""
    track = TrackFactory()
    generated = TrackGeneratedAudio.objects.create(track=track)
    generated.preview_status = TrackGeneratedAudio.ProcessingStatus.BUILDING
    generated.stream_status = TrackGeneratedAudio.ProcessingStatus.READY
    generated.save(update_fields=('preview_status', 'stream_status'))

    with (
        patch.object(
            AudioProcessingService,
            'create_preview',
            side_effect=AudioProcessingError('preview failed'),
        ),
        pytest.raises(AudioProcessingError),
    ):
        TrackAudioPreparationService._prepare_preview(
            generated=generated,
            source_path=tmp_path / 'source.wav',
            target_path=tmp_path / 'preview.mp3',
            source_duration=120,
        )

    generated.refresh_from_db()
    assert generated.preview_status == (
        TrackGeneratedAudio.ProcessingStatus.FAILED
    )
    assert generated.stream_status == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )


@pytest.mark.parametrize(
    ('method_name', 'field_name', 'target_filename'),
    [
        ('_prepare_stream', 'stream_file', 'stream.mp3'),
        ('_prepare_preview', 'preview_file', 'preview.mp3'),
    ],
)
def test_generated_file_is_saved_once(
    tmp_path,
    method_name,
    field_name,
    target_filename,
):
    """Подготовка не загружает один generated-файл дважды."""
    track = TrackFactory()
    generated = TrackGeneratedAudio.objects.create(track=track)
    target_path = tmp_path / target_filename
    target_path.write_bytes(b'generated audio')
    field = getattr(generated, field_name)

    with (
        patch.object(
            AudioProcessingService,
            'create_stream',
            return_value=None,
        ),
        patch.object(
            AudioProcessingService,
            'create_preview',
            return_value=30,
        ),
        patch.object(
            field.storage,
            'save',
            wraps=field.storage.save,
        ) as save_mock,
    ):
        kwargs = {
            'generated': generated,
            'source_path': tmp_path / 'source.wav',
            'target_path': target_path,
        }
        if method_name == '_prepare_preview':
            kwargs['source_duration'] = 120
        getattr(TrackAudioPreparationService, method_name)(**kwargs)

    assert save_mock.call_count == 1


def test_ready_generated_audio_task_is_noop():
    """Повторная задача не пересобирает готовое аудио текущего original."""
    track = TrackFactory(duration=120)
    TrackGeneratedAudio.objects.create(
        track=track,
        preview_file='tracks/preview/ready.mp3',
        preview_status=TrackGeneratedAudio.ProcessingStatus.READY,
        stream_file='tracks/stream/ready.mp3',
        stream_status=TrackGeneratedAudio.ProcessingStatus.READY,
    )

    with (
        patch.object(
            TrackAudioPreparationService,
            '_mark_processing_started',
        ) as mark_started,
        patch.object(
            TrackAudioPreparationService,
            '_download_source_file',
        ) as download,
    ):
        TrackAudioPreparationService.prepare(track.pk)

    mark_started.assert_not_called()
    download.assert_not_called()
