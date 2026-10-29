import hashlib
import subprocess
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.files.storage import FileSystemStorage
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
from store.services.track_upload import (
    TrackUploadService,
    TrackUploadStorageService,
)
from store.tasks.audio import prepare_track_audio
from store.tests.factories import RecordingFactory, make_audio_file

pytestmark = pytest.mark.django_db

V1_CONTENT = b'original audio version one'
V2_CONTENT = b'original audio version two'
V1_DURATION = 101
V2_DURATION = 202


@pytest.fixture
def isolated_audio_storage(settings, tmp_path, monkeypatch):
    """Изолирует original и generated-файлы гонки в одном storage."""
    settings.USE_S3_MEDIA = False
    storage = FileSystemStorage(
        location=tmp_path,
        base_url='/media/',
    )

    for model, field_names in (
        (Recording, ('audio_file',)),
        (TrackGeneratedAudio, ('preview_file', 'stream_file')),
    ):
        for field_name in field_names:
            field = model._meta.get_field(field_name)
            monkeypatch.setattr(field, 'storage', storage)

    return storage


def replace_original(recording: Recording) -> None:
    """Заменяет original на v2 через штатный REPLACE-upload."""
    upload = TrackUploadService.create_replacement_upload(
        recording=recording,
        filename='version-two.flac',
        size=len(V2_CONTENT),
        content_type='audio/flac',
    )
    upload = TrackUploadService.receive_local_file(
        upload=upload,
        uploaded_file=SimpleUploadedFile(
            name='version-two.flac',
            content=V2_CONTENT,
            content_type='audio/flac',
        ),
    )
    TrackUploadStorageService.complete(upload=upload)


def probe_version(source_path):
    """Возвращает различимую длительность для каждой версии original."""
    content = source_path.read_bytes()
    duration = V1_DURATION if content == V1_CONTENT else V2_DURATION
    return AudioMetadata(duration=duration)


def create_versioned_stream(*, source_path, target_path) -> None:
    """Создаёт различимый stream без запуска ffmpeg."""
    target_path.write_bytes(b'stream:' + source_path.read_bytes())


def create_versioned_preview(
    *,
    source_path,
    target_path,
    source_duration,
) -> int:
    """Создаёт различимый preview без запуска ffmpeg."""
    target_path.write_bytes(b'preview:' + source_path.read_bytes())
    return source_duration


def stored_generated_names(storage, directory: str) -> set[str]:
    """Возвращает имена файлов одного каталога generated-аудио."""
    root = Path(storage.location) / directory
    if not root.exists():
        return set()
    return {
        str(path.relative_to(storage.location))
        for path in root.iterdir()
        if path.is_file()
    }


def test_calculate_file_hash_returns_content_sha256():
    """Возвращает SHA-256 содержимого открытого файла."""
    content = b'original audio bytes'

    result = calculate_file_hash(BytesIO(content))

    assert result == hashlib.sha256(content).hexdigest()


def test_prepare_updates_recording_duration_and_hash(isolated_audio_storage):
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
        patch.object(
            AudioProcessingService,
            'create_stream',
            side_effect=create_versioned_stream,
        ),
        patch.object(
            AudioProcessingService,
            'create_preview',
            side_effect=create_versioned_preview,
        ),
    ):
        TrackAudioPreparationService.prepare(recording.pk)

    recording.refresh_from_db()
    generated = TrackGeneratedAudio.objects.get(track=recording)

    assert generated.track == recording
    assert recording.duration == 137
    assert recording.file_hash == hashlib.sha256(content).hexdigest()
    assert generated.preview_status == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )
    assert generated.stream_status == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )


def test_stale_worker_does_not_overwrite_newer_audio_processing_results(
    isolated_audio_storage,
    django_capture_on_commit_callbacks,
):
    """Поздний успешный воркер v1 не заменяет результаты v2."""
    storage = isolated_audio_storage
    recording = RecordingFactory(
        audio_file=make_audio_file(
            name='version-one.flac',
            content=V1_CONTENT,
        ),
    )
    original_download = TrackAudioPreparationService._download_source_file
    race_state = {'download_calls': 0}

    def download_with_interleaving(*, recording, workdir) -> tuple[Path, str]:
        source = original_download(
            recording=recording,
            workdir=workdir,
        )
        race_state['download_calls'] += 1

        if race_state['download_calls'] == 1:
            replace_original(recording)
            TrackAudioPreparationService.prepare(recording.pk)

            current_recording = Recording.objects.get(pk=recording.pk)
            current_generated = TrackGeneratedAudio.objects.get(
                track=recording,
            )
            race_state.update(
                v2_duration=current_recording.duration,
                v2_hash=current_recording.file_hash,
                v2_preview_name=current_generated.preview_file.name,
                v2_stream_name=current_generated.stream_file.name,
                v2_preview_status=current_generated.preview_status,
                v2_stream_status=current_generated.stream_status,
            )

        return source

    with (
        patch.object(TrackGeneratedAudioScheduler, 'schedule'),
        patch.object(
            TrackAudioPreparationService,
            '_download_source_file',
            side_effect=download_with_interleaving,
        ),
        patch.object(
            AudioProcessingService,
            'probe_metadata',
            side_effect=probe_version,
        ),
        patch.object(
            AudioProcessingService,
            'create_stream',
            side_effect=create_versioned_stream,
        ),
        patch.object(
            AudioProcessingService,
            'create_preview',
            side_effect=create_versioned_preview,
        ),
        patch.object(storage, 'delete', wraps=storage.delete) as delete_mock,
        django_capture_on_commit_callbacks(execute=True),
    ):
        TrackAudioPreparationService.prepare(recording.pk)

    recording.refresh_from_db()
    generated = TrackGeneratedAudio.objects.get(track=recording)

    assert race_state['download_calls'] == 2
    assert race_state['v2_duration'] == V2_DURATION
    assert race_state['v2_hash'] == hashlib.sha256(V2_CONTENT).hexdigest()
    assert race_state['v2_preview_status'] == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )
    assert race_state['v2_stream_status'] == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )

    with recording.audio_file.open('rb') as audio_file:
        assert audio_file.read() == V2_CONTENT

    assert recording.duration == V2_DURATION
    assert recording.file_hash == hashlib.sha256(V2_CONTENT).hexdigest()
    assert generated.preview_status == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )
    assert generated.stream_status == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )
    assert generated.preview_error == ''
    assert generated.stream_error == ''
    assert generated.preview_duration == V2_DURATION
    assert generated.preview_file.name == race_state['v2_preview_name']
    assert generated.stream_file.name == race_state['v2_stream_name']

    with generated.preview_file.open('rb') as preview_file:
        assert preview_file.read() == b'preview:' + V2_CONTENT
    with generated.stream_file.open('rb') as stream_file:
        assert stream_file.read() == b'stream:' + V2_CONTENT

    assert storage.exists(race_state['v2_preview_name'])
    assert storage.exists(race_state['v2_stream_name'])
    deleted_names = {item.args[0] for item in delete_mock.call_args_list}
    assert race_state['v2_preview_name'] not in deleted_names
    assert race_state['v2_stream_name'] not in deleted_names
    assert stored_generated_names(
        storage,
        'recordings/preview',
    ) == {race_state['v2_preview_name']}
    assert stored_generated_names(
        storage,
        'recordings/stream',
    ) == {race_state['v2_stream_name']}


def test_stale_worker_failure_does_not_overwrite_newer_ready_statuses(
    isolated_audio_storage,
    django_capture_on_commit_callbacks,
):
    """Поздняя ошибка воркера v1 не меняет READY и файлы v2."""
    storage = isolated_audio_storage
    recording = RecordingFactory(
        audio_file=make_audio_file(
            name='version-one.flac',
            content=V1_CONTENT,
        ),
    )
    original_download = TrackAudioPreparationService._download_source_file
    race_state = {'download_calls': 0}

    def download_with_interleaving(*, recording, workdir) -> tuple[Path, str]:
        source = original_download(
            recording=recording,
            workdir=workdir,
        )
        race_state['download_calls'] += 1

        if race_state['download_calls'] == 1:
            replace_original(recording)
            TrackAudioPreparationService.prepare(recording.pk)

            current_generated = TrackGeneratedAudio.objects.get(
                track=recording,
            )
            race_state.update(
                v2_preview_name=current_generated.preview_file.name,
                v2_stream_name=current_generated.stream_file.name,
                v2_preview_status=current_generated.preview_status,
                v2_stream_status=current_generated.stream_status,
            )

        return source

    def probe_with_stale_failure(source_path) -> AudioMetadata:
        if source_path.read_bytes() == V1_CONTENT:
            raise ValueError('stale v1 failed')
        return AudioMetadata(duration=V2_DURATION)

    with (
        patch.object(TrackGeneratedAudioScheduler, 'schedule'),
        patch.object(
            TrackAudioPreparationService,
            '_download_source_file',
            side_effect=download_with_interleaving,
        ),
        patch.object(
            AudioProcessingService,
            'probe_metadata',
            side_effect=probe_with_stale_failure,
        ),
        patch.object(
            AudioProcessingService,
            'create_stream',
            side_effect=create_versioned_stream,
        ),
        patch.object(
            AudioProcessingService,
            'create_preview',
            side_effect=create_versioned_preview,
        ),
        patch.object(storage, 'delete', wraps=storage.delete) as delete_mock,
        django_capture_on_commit_callbacks(execute=True),
    ):
        TrackAudioPreparationService.prepare(recording.pk)

    recording.refresh_from_db()
    generated = TrackGeneratedAudio.objects.get(track=recording)

    assert race_state['download_calls'] == 2
    assert race_state['v2_preview_status'] == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )
    assert race_state['v2_stream_status'] == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )

    with recording.audio_file.open('rb') as audio_file:
        assert audio_file.read() == V2_CONTENT

    assert recording.duration == V2_DURATION
    assert recording.file_hash == hashlib.sha256(V2_CONTENT).hexdigest()
    assert generated.preview_file.name == race_state['v2_preview_name']
    assert generated.stream_file.name == race_state['v2_stream_name']
    assert generated.preview_status == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )
    assert generated.stream_status == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )
    assert generated.preview_error == ''
    assert generated.stream_error == ''

    with generated.preview_file.open('rb') as preview_file:
        assert preview_file.read() == b'preview:' + V2_CONTENT
    with generated.stream_file.open('rb') as stream_file:
        assert stream_file.read() == b'stream:' + V2_CONTENT

    assert storage.exists(race_state['v2_preview_name'])
    assert storage.exists(race_state['v2_stream_name'])
    deleted_names = {item.args[0] for item in delete_mock.call_args_list}
    assert race_state['v2_preview_name'] not in deleted_names
    assert race_state['v2_stream_name'] not in deleted_names
    assert stored_generated_names(
        storage,
        'recordings/preview',
    ) == {race_state['v2_preview_name']}
    assert stored_generated_names(
        storage,
        'recordings/stream',
    ) == {race_state['v2_stream_name']}


@pytest.mark.parametrize('failed_component', ('preview', 'stream'))
def test_prepare_preserves_partial_success(
    failed_component,
    isolated_audio_storage,
    django_capture_on_commit_callbacks,
):
    """Ошибка одного generated-файла не портит успешно созданный второй."""
    recording = RecordingFactory(
        audio_file=make_audio_file(
            name='version-one.flac',
            content=V1_CONTENT,
        ),
    )

    def create_stream(*, source_path, target_path) -> None:
        if failed_component == 'stream':
            raise ValueError('stream failed')
        create_versioned_stream(
            source_path=source_path,
            target_path=target_path,
        )

    def create_preview(
        *,
        source_path,
        target_path,
        source_duration,
    ) -> int:
        if failed_component == 'preview':
            raise ValueError('preview failed')
        return create_versioned_preview(
            source_path=source_path,
            target_path=target_path,
            source_duration=source_duration,
        )

    with (
        patch.object(
            AudioProcessingService,
            'probe_metadata',
            return_value=AudioMetadata(duration=V1_DURATION),
        ),
        patch.object(
            AudioProcessingService,
            'create_stream',
            side_effect=create_stream,
        ),
        patch.object(
            AudioProcessingService,
            'create_preview',
            side_effect=create_preview,
        ),
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(ValueError, match=f'{failed_component} failed'),
    ):
        TrackAudioPreparationService.prepare(recording.pk)

    recording.refresh_from_db()
    generated = TrackGeneratedAudio.objects.get(track=recording)
    successful_component = (
        'stream' if failed_component == 'preview' else 'preview'
    )

    assert recording.duration == V1_DURATION
    assert recording.file_hash == hashlib.sha256(V1_CONTENT).hexdigest()
    assert getattr(generated, f'{failed_component}_status') == (
        TrackGeneratedAudio.ProcessingStatus.FAILED
    )
    assert getattr(generated, f'{failed_component}_error') == (
        f'{failed_component} failed'
    )
    assert getattr(generated, f'{successful_component}_status') == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )
    assert getattr(generated, f'{successful_component}_error') == ''
    assert getattr(generated, f'{successful_component}_file')


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
    isolated_audio_storage,
    django_capture_on_commit_callbacks,
):
    """После успешной замены stream удаляется прежний объект storage."""
    recording = RecordingFactory(
        audio_file=make_audio_file(
            name='version-one.flac',
            content=V1_CONTENT,
        ),
    )
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

    with (
        patch.object(
            AudioProcessingService,
            'probe_metadata',
            return_value=AudioMetadata(duration=V1_DURATION),
        ),
        patch.object(
            AudioProcessingService,
            'create_stream',
            side_effect=create_versioned_stream,
        ),
        patch.object(
            AudioProcessingService,
            'create_preview',
            side_effect=create_versioned_preview,
        ),
        patch.object(storage, 'delete', wraps=storage.delete) as delete_mock,
    ):
        with django_capture_on_commit_callbacks(execute=True):
            TrackAudioPreparationService.prepare(recording.pk)
            delete_mock.assert_not_called()

    generated.refresh_from_db()

    assert generated.stream_file.name != old_name
    assert generated.stream_status == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )
    delete_mock.assert_called_once_with(old_name)
    assert not storage.exists(old_name)


def test_failed_stream_upload_keeps_old_file(
    isolated_audio_storage,
    django_capture_on_commit_callbacks,
):
    """Ошибка сохранения нового stream не удаляет предыдущий файл."""
    recording = RecordingFactory(
        audio_file=make_audio_file(
            name='version-one.flac',
            content=V1_CONTENT,
        ),
    )
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
    original_save = storage.save

    def save_with_stream_failure(name, content, max_length=None) -> str:
        if name.startswith('recordings/stream/'):
            raise OSError('Storage unavailable')
        return original_save(name, content, max_length=max_length)

    with (
        patch.object(
            AudioProcessingService,
            'probe_metadata',
            return_value=AudioMetadata(duration=V1_DURATION),
        ),
        patch.object(
            AudioProcessingService,
            'create_stream',
            side_effect=create_versioned_stream,
        ),
        patch.object(
            AudioProcessingService,
            'create_preview',
            side_effect=create_versioned_preview,
        ),
        patch.object(storage, 'save', side_effect=save_with_stream_failure),
        patch.object(storage, 'delete') as delete_mock,
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(OSError),
    ):
        TrackAudioPreparationService.prepare(recording.pk)

    generated.refresh_from_db()

    assert generated.stream_file.name == old_name
    assert generated.stream_status == (
        TrackGeneratedAudio.ProcessingStatus.FAILED
    )
    assert generated.stream_error == 'Storage unavailable'
    assert generated.preview_status == (
        TrackGeneratedAudio.ProcessingStatus.READY
    )
    assert storage.exists(old_name)
    delete_mock.assert_not_called()
