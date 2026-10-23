"""Тесты maintenance-задач для мастер-записей."""

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.files.storage import FileSystemStorage

from store.models import Recording, TrackGeneratedAudio
from store.services.audio import calculate_file_hash
from store.tasks.maintenance import (
    backfill_missing_recording_hashes,
    schedule_missing_track_audio,
)
from store.tests.factories import RecordingFactory, make_audio_file

pytestmark = pytest.mark.django_db


def test_schedule_missing_track_audio_uses_recordings():
    """Планирует Recording с original и отсутствующей/ошибочной генерацией."""
    missing_generated = RecordingFactory(name='Missing generated')
    empty_original = RecordingFactory(
        name='Empty original',
        audio_file='',
    )
    ready = RecordingFactory(name='Ready')
    failed_preview = RecordingFactory(name='Failed preview')
    failed_stream = RecordingFactory(name='Failed stream')

    TrackGeneratedAudio.objects.create(
        track=ready,
        preview_status=TrackGeneratedAudio.ProcessingStatus.READY,
        stream_status=TrackGeneratedAudio.ProcessingStatus.READY,
    )
    TrackGeneratedAudio.objects.create(
        track=failed_preview,
        preview_status=TrackGeneratedAudio.ProcessingStatus.FAILED,
        stream_status=TrackGeneratedAudio.ProcessingStatus.READY,
    )
    TrackGeneratedAudio.objects.create(
        track=failed_stream,
        preview_status=TrackGeneratedAudio.ProcessingStatus.READY,
        stream_status=TrackGeneratedAudio.ProcessingStatus.FAILED,
    )

    with patch(
        'store.tasks.maintenance.TrackGeneratedAudioScheduler.schedule',
    ) as schedule_mock:
        result = schedule_missing_track_audio.run()

    assert result == {'candidates': 3}
    scheduled_ids = {call.args[0].pk for call in schedule_mock.call_args_list}
    assert scheduled_ids == {
        missing_generated.pk,
        failed_preview.pk,
        failed_stream.pk,
    }
    assert empty_original.pk not in scheduled_ids
    assert ready.pk not in scheduled_ids


def test_backfill_missing_recording_hashes_handles_updates_races_and_errors(
    tmp_path,
    monkeypatch,
):
    """Backfill считает итоги, пропускает race и продолжает после ошибки."""
    storage = FileSystemStorage(
        location=tmp_path,
        base_url='/private/',
    )
    audio_file_field = Recording._meta.get_field('audio_file')
    monkeypatch.setattr(audio_file_field, 'storage', storage)

    first_content = b'first original'
    after_error_content = b'processed after error'
    first = RecordingFactory(
        name='A first',
        audio_file=make_audio_file(
            name='first.mp3',
            content=first_content,
        ),
        file_hash='',
    )
    race = RecordingFactory(
        name='B race',
        audio_file=make_audio_file(
            name='race.mp3',
            content=b'racing original',
        ),
        file_hash='',
    )
    failed = RecordingFactory(
        name='C failed',
        audio_file=make_audio_file(
            name='failed.mp3',
            content=b'unreadable original',
        ),
        file_hash='',
    )
    after_error = RecordingFactory(
        name='D after error',
        audio_file=make_audio_file(
            name='after-error.mp3',
            content=after_error_content,
        ),
        file_hash='',
    )
    existing = RecordingFactory(
        name='E existing',
        file_hash='already-filled',
    )
    empty_original = RecordingFactory(
        name='F empty',
        audio_file='',
        file_hash='',
    )

    original_open = storage.open

    def open_file(name: str, mode: str = 'rb') -> object:
        if name == failed.audio_file.name:
            raise OSError('Storage unavailable')
        return original_open(name, mode)

    def calculate_with_race(source_file) -> str:
        if Path(source_file.name).name == Path(race.audio_file.name).name:
            Recording.objects.filter(pk=race.pk).update(
                audio_file='recordings/original/replaced.mp3',
            )
        return calculate_file_hash(source_file)

    with (
        patch.object(storage, 'open', side_effect=open_file),
        patch(
            'store.tasks.maintenance.calculate_file_hash',
            side_effect=calculate_with_race,
        ),
        patch(
            'store.tasks.maintenance.TrackGeneratedAudioScheduler.schedule',
        ) as schedule_mock,
    ):
        result = backfill_missing_recording_hashes.run()

    assert result == {
        'candidates': 4,
        'updated': 2,
        'skipped': 1,
        'errors': 1,
    }

    first.refresh_from_db()
    race.refresh_from_db()
    failed.refresh_from_db()
    after_error.refresh_from_db()
    existing.refresh_from_db()
    empty_original.refresh_from_db()

    assert first.file_hash == hashlib.sha256(first_content).hexdigest()
    assert race.audio_file.name == 'recordings/original/replaced.mp3'
    assert race.file_hash == ''
    assert failed.file_hash == ''
    assert (
        after_error.file_hash
        == hashlib.sha256(
            after_error_content,
        ).hexdigest()
    )
    assert existing.file_hash == 'already-filled'
    assert empty_original.file_hash == ''
    assert TrackGeneratedAudio.objects.count() == 0
    schedule_mock.assert_not_called()
