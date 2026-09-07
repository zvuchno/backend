import subprocess
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

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
