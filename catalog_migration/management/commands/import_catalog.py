"""Единый последовательный запуск migration-v1.3."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any, Callable

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from catalog_migration.services.catalog_audio_import import (
    CatalogAudioImporter,
)
from catalog_migration.services.catalog_bundle import bundle_root
from catalog_migration.services.catalog_digital_product_import import (
    CatalogDigitalProductImporter,
)
from catalog_migration.services.catalog_image_import import (
    CatalogImageImporter,
)
from catalog_migration.services.catalog_merch_import import (
    CatalogMerchImporter,
)
from catalog_migration.services.catalog_migration_preflight import (
    CatalogMigrationPreflight,
)
from catalog_migration.services.catalog_package import (
    DEFAULT_S3_PACKAGE_PREFIX,
    CatalogPackageError,
    CatalogPackagePreparer,
)
from catalog_migration.services.catalog_profile_extras_import import (
    CatalogProfileExtrasImporter,
)
from catalog_migration.services.catalog_profile_import import (
    CatalogProfileImporter,
)
from catalog_migration.services.catalog_release_import import (
    CatalogReleaseImporter,
)
from catalog_migration.services.catalog_track_import import (
    CatalogTrackImporter,
)

DEFAULT_PACKAGE_ROOT = Path('/app/media/private/migration/v1.3')


@dataclass(frozen=True)
class _Stage:
    name: str
    enabled: Callable[[dict[str, bool]], bool]
    importer: type
    media: bool = False


STAGES = (
    _Stage(
        'profiles',
        lambda enabled: enabled.get('profiles', False),
        CatalogProfileImporter,
    ),
    _Stage(
        'releases',
        lambda enabled: enabled.get('releases', False),
        CatalogReleaseImporter,
    ),
    _Stage(
        'tracks',
        lambda enabled: enabled.get('tracks', False),
        CatalogTrackImporter,
    ),
    _Stage(
        'merch',
        lambda enabled: enabled.get('merch', False),
        CatalogMerchImporter,
    ),
    _Stage(
        'digital_products',
        lambda enabled: (
            enabled.get('releases', False) or enabled.get('tracks', False)
        ),
        CatalogDigitalProductImporter,
    ),
    _Stage(
        'profile_extras',
        lambda enabled: any(
            enabled.get(name, False)
            for name in ('public_contacts', 'telegram', 'cdek')
        ),
        CatalogProfileExtrasImporter,
    ),
    _Stage(
        'images',
        lambda enabled: any(
            enabled.get(name, False)
            for name in ('profiles', 'releases', 'merch')
        ),
        CatalogImageImporter,
        media=True,
    ),
    _Stage(
        'audio',
        lambda enabled: enabled.get('tracks', False),
        CatalogAudioImporter,
        media=True,
    ),
)


class _StageProgress:
    """Печатает компактный прогресс и heartbeat длительного этапа."""

    def __init__(
        self,
        command: Command,
        stage: _Stage,
        heartbeat_seconds: float,
    ):
        self.command = command
        self.stage = stage
        self.heartbeat_seconds = heartbeat_seconds
        self.processed = 0
        self.total: int | None = None
        self.last_printed = 0
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._heartbeat, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        self._thread.join(timeout=min(self.heartbeat_seconds, 1))

    def update(self, processed: int, total: int) -> None:
        with self._lock:
            first_total = self.total is None
            self.processed = processed
            self.total = total
            step = max(1, total // 20)
            should_print = (
                processed == total or processed - self.last_printed >= step
            )
            if should_print:
                self.last_printed = processed
        if first_total:
            self.command._write(f'[{self.stage.name}] всего объектов: {total}')
        if should_print and processed:
            self.command._write(
                f'[{self.stage.name}] обработано {processed}/{total}',
            )

    def snapshot(self) -> tuple[int, int | None]:
        with self._lock:
            return self.processed, self.total

    def _heartbeat(self) -> None:
        while not self._stopped.wait(self.heartbeat_seconds):
            processed, total = self.snapshot()
            if total is None:
                message = 'проверка входных данных ещё выполняется'
            elif self.stage.media and processed < total:
                message = (
                    'операция с медиафайлом ещё выполняется: '
                    f'обработано {processed}/{total}'
                )
            else:
                message = (
                    f'этап ещё выполняется: обработано {processed}/{total}'
                )
            self.command._write(f'[{self.stage.name}] {message}')


class Command(BaseCommand):
    """Последовательно запускает существующие импортёры каталога."""

    help = 'Импортировать включённые этапы каталога migration-v1.3'
    heartbeat_seconds = 30.0

    def add_arguments(self, parser):
        parser.add_argument(
            'package_root',
            nargs='?',
            type=Path,
            default=DEFAULT_PACKAGE_ROOT,
            help=f'Пакет миграции (по умолчанию {DEFAULT_PACKAGE_ROOT})',
        )
        parser.add_argument(
            '--retry-errors',
            action='store_true',
            help='Разрешить штатный повтор ошибочных состояний аудио',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Проверить полный план без записей в БД, media и Celery',
        )
        parser.add_argument(
            '--s3-prefix',
            default=DEFAULT_S3_PACKAGE_PREFIX,
            help='Префикс пакета в приватном S3 (по умолчанию migration-v2)',
        )

    def handle(self, *args, **options):
        requested_root = options['package_root'].expanduser()
        preparer = CatalogPackagePreparer(s3_prefix=options['s3_prefix'])
        try:
            with preparer.prepare(requested_root) as package_root:
                self._handle_package(package_root, options)
        except CatalogPackageError as error:
            raise CommandError(
                f'Подготовка пакета не выполнена: {error}',
            ) from error

    def _handle_package(
        self,
        package_root: Path,
        options: dict[str, Any],
    ) -> None:
        enabled = self._read_enabled(package_root)
        selected = tuple(stage for stage in STAGES if stage.enabled(enabled))
        selected_names = ', '.join(stage.name for stage in selected) or '-'

        self._write('IMPORT CATALOG START')
        package_label = (
            f's3:{options["s3_prefix"].strip("/")}'
            if settings.USE_S3_MEDIA
            else str(package_root)
        )
        self._write(f'package={package_label}')
        self._write(f'stages={selected_names}')

        preflight = CatalogMigrationPreflight(package_root).run()
        if not preflight.passed:
            raise CommandError(preflight.render())
        if options['dry_run']:
            self._write(preflight.render())
            self._write(
                'IMPORT CATALOG DRY-RUN COMPLETE; '
                'этапы импорта и записи не запускались',
            )
            return

        for stage in selected:
            self._run_stage(
                stage,
                package_root,
                retry_errors=options['retry_errors'],
                dry_run=options['dry_run'],
                s3_prefix=options['s3_prefix'],
            )

        self._write('IMPORT CATALOG COMPLETE')

    def _run_stage(
        self,
        stage: _Stage,
        package_root: Path,
        *,
        retry_errors: bool,
        dry_run: bool,
        s3_prefix: str,
    ) -> None:
        started_at = monotonic()
        self._write(f'[{stage.name}] начало')
        progress = _StageProgress(self, stage, self.heartbeat_seconds)
        progress.start()
        importer_options: dict[str, Any] = {
            'progress_callback': progress.update,
            'dry_run': dry_run,
        }
        if stage.name == 'audio':
            importer_options['retry_errors'] = retry_errors
            if settings.USE_S3_MEDIA:
                importer_options['source_prefix'] = s3_prefix
        elif stage.name == 'images' and settings.USE_S3_MEDIA:
            importer_options['source_prefix'] = (
                f'{s3_prefix.strip("/")}/{bundle_root(package_root).name}'
            )

        try:
            result = stage.importer(package_root, **importer_options).run()
        except Exception as error:
            progress.stop()
            processed, total = progress.snapshot()
            elapsed = monotonic() - started_at
            total_text = '?' if total is None else str(total)
            self._write(
                f'[{stage.name}] ошибка: обработано {processed}/{total_text}; '
                f'ошибок=1; время={elapsed:.1f}s',
            )
            raise CommandError(
                f'Этап {stage.name} завершился ошибкой: {error}',
            ) from error

        progress.stop()
        processed, total = progress.snapshot()
        if total is None:
            processed = total = self._result_total(stage.name, result)
        elapsed = monotonic() - started_at
        counters = self._result_counters(stage.name, result)
        self._write(
            f'[{stage.name}] завершён: обработано {processed}/{total}; '
            f'{counters}; время={elapsed:.1f}s',
        )
        if stage.name == 'audio':
            self._write(
                f'[audio] оригиналов подключено и задач поставлено в Celery: '
                f'{result.queued}',
            )
            if result.selected and result.ready == result.selected:
                self._write(
                    f'[audio] preview/stream готовы: '
                    f'{result.ready}/{result.selected}',
                )
            elif result.selected == 0:
                self._write('[audio] аудиофайлы не выбраны')
            else:
                self._write(
                    '[audio] preview/stream продолжают обрабатываться '
                    'асинхронно; аудиокаталог ещё не объявлен готовым',
                )

    def _write(self, message: str) -> None:
        self.stdout.write(message)
        self.stdout.flush()

    @staticmethod
    def _read_enabled(package_root: Path) -> dict[str, bool]:
        config_path = package_root / 'import_config.json'
        try:
            document = json.loads(config_path.read_text(encoding='utf-8'))
            enabled = document['enabled']
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise CommandError(
                f'Не удалось прочитать конфигурацию пакета: {config_path}',
            ) from error
        if not isinstance(enabled, dict):
            raise CommandError(
                f'Некорректный enabled в конфигурации пакета: {config_path}',
            )
        return enabled

    @staticmethod
    def _result_total(stage: str, result: Any) -> int:
        if stage == 'merch':
            return result.selected_merch
        if stage == 'digital_products':
            return result.selected_albums + result.selected_tracks
        if stage == 'profile_extras':
            return sum(
                getattr(result, name).selected
                for name in ('contacts', 'socials', 'telegram', 'cdek')
            )
        if stage == 'images':
            return sum(result.selected.values())
        return result.selected

    @staticmethod
    def _result_counters(stage: str, result: Any) -> str:
        if stage in {'profiles', 'releases', 'tracks'}:
            return (
                f'создано={result.created}; '
                f'пропущено={result.already_mapped}; ошибок=0'
            )
        if stage == 'merch':
            return (
                f'создано Merch={result.created_merch}, '
                f'Product={result.created_products}, '
                f'Variant={result.created_variants}; '
                f'пропущено={result.already_mapped}; ошибок=0'
            )
        if stage == 'digital_products':
            skipped = result.already_mapped + result.adopted_products
            return (
                f'создано Product={result.created_products}, '
                f'Variant={result.created_variants}; '
                f'пропущено={skipped}; ошибок=0'
            )
        if stage == 'profile_extras':
            categories = ('contacts', 'socials', 'telegram', 'cdek')
            created = sum(getattr(result, name).created for name in categories)
            skipped = sum(
                getattr(result, name).existing for name in categories
            )
            return f'создано={created}; пропущено={skipped}; ошибок=0'
        if stage == 'images':
            created = sum(result.created.values())
            skipped = sum(result.existing.values())
            return f'создано={created}; пропущено={skipped}; ошибок=0'
        if stage == 'audio':
            skipped = result.ready + result.processing
            return (
                f'оригиналов_подключено={result.queued}; '
                f'пропущено={skipped}; ошибок={result.failed}'
            )
        raise AssertionError(f'Неизвестный этап: {stage}')
