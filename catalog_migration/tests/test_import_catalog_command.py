"""Точечные тесты единой команды миграции каталога."""

import json
import time
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Never
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from catalog_migration.management.commands.import_catalog import (
    STAGES,
    _Stage,
)
from catalog_migration.tests.test_catalog_package import FakeS3Client


@pytest.fixture(autouse=True)
def _successful_preflight(monkeypatch) -> None:
    """Keep package validation outside these orchestration tests."""
    result = SimpleNamespace(passed=True, render=lambda: 'PREFLIGHT PASS')
    monkeypatch.setattr(
        'catalog_migration.management.commands.import_catalog.'
        'CatalogMigrationPreflight.run',
        lambda self: result,
    )


def _result(stage: str) -> Any:
    if stage in {'profiles', 'releases', 'tracks'}:
        return SimpleNamespace(selected=2, created=1, already_mapped=1)
    if stage == 'merch':
        return SimpleNamespace(
            selected_merch=2,
            created_merch=1,
            created_products=1,
            created_variants=2,
            already_mapped=1,
        )
    if stage == 'digital_products':
        return SimpleNamespace(
            selected_albums=1,
            selected_tracks=1,
            created_products=1,
            created_variants=1,
            adopted_products=0,
            already_mapped=1,
        )
    if stage == 'profile_extras':
        category = SimpleNamespace(selected=1, created=1, existing=0)
        return SimpleNamespace(
            contacts=category,
            socials=category,
            telegram=category,
            cdek=category,
        )
    if stage == 'images':
        return SimpleNamespace(
            selected={'profile': 1, 'release': 1},
            created={'profile': 1},
            existing={'release': 1},
        )
    return SimpleNamespace(
        selected=2,
        queued=1,
        ready=1,
        processing=0,
        failed=0,
    )


def _write_config(package: Path, enabled: dict[str, bool]) -> None:
    package.mkdir()
    (package / 'import_config.json').write_text(
        json.dumps({'enabled': enabled}),
        encoding='utf-8',
    )


def test_runs_enabled_stages_in_dependency_order(tmp_path) -> None:
    """Выполняет только включённые этапы в порядке зависимостей."""
    package = tmp_path / 'migration-v1.3'
    _write_config(
        package,
        {
            'profiles': True,
            'releases': True,
            'tracks': True,
            'merch': True,
            'public_contacts': True,
            'telegram': True,
            'cdek': True,
        },
    )
    calls = []

    def fake_importer(stage: str) -> type:
        class Importer:
            def __init__(self, package_root, **options):
                assert package_root == package
                assert options['dry_run'] is False
                self.progress = options['progress_callback']

            def run(self) -> Any:
                calls.append(stage)
                self.progress(0, 2)
                self.progress(2, 2)
                return _result(stage)

        return Importer

    stages = tuple(
        _Stage(
            stage.name,
            stage.enabled,
            fake_importer(stage.name),
            stage.media,
        )
        for stage in STAGES
    )
    output = StringIO()
    with patch(
        'catalog_migration.management.commands.import_catalog.STAGES',
        stages,
    ):
        call_command('import_catalog', package, stdout=output)

    assert calls == [
        'profiles',
        'releases',
        'tracks',
        'merch',
        'digital_products',
        'profile_extras',
        'images',
        'audio',
    ]
    text = output.getvalue()
    assert 'IMPORT CATALOG START' in text
    assert (
        '[audio] оригиналов подключено и задач поставлено в Celery: 1' in text
    )
    assert 'preview/stream продолжают обрабатываться асинхронно' in text
    assert text.rstrip().endswith('IMPORT CATALOG COMPLETE')


def test_stops_on_stage_error(tmp_path) -> None:
    """Останавливается на первой ошибке и называет этап."""
    package = tmp_path / 'migration-v1.3'
    _write_config(package, {'profiles': True, 'releases': True})
    calls = []

    class PassingImporter:
        def __init__(self, package_root, **options):
            self.progress = options['progress_callback']

        def run(self) -> Any:
            calls.append('profiles')
            self.progress(0, 1)
            self.progress(1, 1)
            return _result('profiles')

    class FailingImporter:
        def __init__(self, package_root, **options):
            pass

        def run(self) -> Never:
            calls.append('releases')
            raise RuntimeError('validation failed')

    stages = (
        _Stage('profiles', lambda enabled: True, PassingImporter),
        _Stage('releases', lambda enabled: True, FailingImporter),
    )
    output = StringIO()
    with patch(
        'catalog_migration.management.commands.import_catalog.STAGES',
        stages,
    ):
        with pytest.raises(CommandError, match='Этап releases'):
            call_command('import_catalog', package, stdout=output)

    assert calls == ['profiles', 'releases']
    assert '[releases] ошибка:' in output.getvalue()


def test_media_stage_prints_heartbeat(tmp_path) -> None:
    """Сообщает, что текущий медиафайл всё ещё обрабатывается."""
    package = tmp_path / 'migration-v1.3'
    _write_config(package, {'profiles': True})

    class SlowImageImporter:
        def __init__(self, package_root, **options):
            self.progress = options['progress_callback']

        def run(self) -> Any:
            self.progress(0, 2)
            time.sleep(0.04)
            self.progress(2, 2)
            return _result('images')

    stages = (
        _Stage('images', lambda enabled: True, SlowImageImporter, media=True),
    )
    output = StringIO()
    with (
        patch(
            'catalog_migration.management.commands.import_catalog.STAGES',
            stages,
        ),
        patch(
            'catalog_migration.management.commands.import_catalog.'
            'Command.heartbeat_seconds',
            0.01,
        ),
    ):
        call_command('import_catalog', package, stdout=output)

    assert (
        '[images] операция с медиафайлом ещё выполняется: обработано 0/2'
        in output.getvalue()
    )


def test_corrupt_s3_config_stops_before_any_stage(settings) -> None:
    """Reject corrupt S3 metadata before constructing an importer."""
    settings.USE_S3_MEDIA = True
    client = FakeS3Client({
        'migration-v2/import_config.json': b'{broken',
    })
    called = False

    class UnexpectedImporter:
        def __init__(self, *args, **kwargs):
            nonlocal called
            called = True

    stage = _Stage('profiles', lambda enabled: True, UnexpectedImporter)
    with (
        patch(
            'catalog_migration.management.commands.import_catalog.STAGES',
            (stage,),
        ),
        patch(
            'catalog_migration.services.catalog_package.'
            'CatalogPackagePreparer._get_s3_client',
            return_value=client,
        ),
        pytest.raises(CommandError, match='Подготовка пакета'),
    ):
        call_command('import_catalog')

    assert called is False


def test_dry_run_stops_after_package_preflight(tmp_path) -> None:
    """Keep the unified dry-run read-only on an empty database."""
    package = tmp_path / 'migration-v2'
    _write_config(package, {'profiles': True})
    called = False

    class UnexpectedImporter:
        def __init__(self, *args, **kwargs):
            nonlocal called
            called = True

    stage = _Stage('profiles', lambda enabled: True, UnexpectedImporter)
    output = StringIO()
    with patch(
        'catalog_migration.management.commands.import_catalog.STAGES',
        (stage,),
    ):
        call_command('import_catalog', package, dry_run=True, stdout=output)

    assert called is False
    assert 'PREFLIGHT' in output.getvalue()
    assert 'этапы импорта и записи не запускались' in output.getvalue()


def test_audio_stage_reports_fully_ready_catalog(tmp_path) -> None:
    """Не сообщает об асинхронной обработке, когда всё уже READY."""
    package = tmp_path / 'migration-v1.3'
    _write_config(package, {'tracks': True})

    class ReadyAudioImporter:
        def __init__(self, package_root, **options):
            self.progress = options['progress_callback']

        def run(self) -> Any:
            self.progress(2, 2)
            return SimpleNamespace(
                selected=2,
                queued=0,
                ready=2,
                processing=0,
                failed=0,
            )

    output = StringIO()
    stage = _Stage(
        'audio',
        lambda enabled: True,
        ReadyAudioImporter,
        media=True,
    )
    with patch(
        'catalog_migration.management.commands.import_catalog.STAGES',
        (stage,),
    ):
        call_command('import_catalog', package, stdout=output)

    text = output.getvalue()
    assert '[audio] preview/stream готовы: 2/2' in text
    assert 'продолжают обрабатываться асинхронно' not in text
