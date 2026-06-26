import subprocess
from unittest.mock import patch

from store.services.audio import AudioProcessingService


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
