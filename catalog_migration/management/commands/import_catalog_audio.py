"""Команда подключения аудио к импортированным Track."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog_migration.services.catalog_audio_import import (
    DEFAULT_SOURCE_PREFIX,
    CatalogAudioImportError,
    CatalogAudioImporter,
)


class Command(BaseCommand):
    """Запускает возобновляемый REPLACE-upload аудио."""

    help = 'Подключить аудио migration-v1.3 к существующим Track'

    def add_arguments(self, parser):
        parser.add_argument('package_root', type=Path)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--track-entity-id')
        parser.add_argument('--retry-errors', action='store_true')
        parser.add_argument(
            '--source-prefix',
            default=DEFAULT_SOURCE_PREFIX,
            help='Префикс приватного S3-пакета без имени bundle',
        )

    def handle(self, *args, **options):
        try:
            result = CatalogAudioImporter(
                options['package_root'],
                dry_run=options['dry_run'],
                track_entity_id=options['track_entity_id'],
                retry_errors=options['retry_errors'],
                source_prefix=options['source_prefix'],
            ).run()
        except CatalogAudioImportError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(result.preflight.render())
        self.stdout.write(result.render())
