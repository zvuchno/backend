"""Команда импорта изображений каталога migration-v1.3."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog_migration.services.catalog_image_import import (
    DEFAULT_SOURCE_PREFIX,
    CatalogImageImportError,
    CatalogImageImporter,
)


class Command(BaseCommand):
    """Импортирует обложки и изображения ранее созданных сущностей."""

    help = 'Импортировать изображения каталога migration-v1.3'

    def add_arguments(self, parser):
        parser.add_argument('package_root', type=Path)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--asset-id',
            help='Импортировать ровно один asset внутри whitelist',
        )
        parser.add_argument(
            '--source-prefix',
            default=DEFAULT_SOURCE_PREFIX,
            help='Префикс приватного S3-пакета без bundle_path',
        )

    def handle(self, *args, **options):
        try:
            result = CatalogImageImporter(
                options['package_root'],
                dry_run=options['dry_run'],
                asset_id=options['asset_id'],
                source_prefix=options['source_prefix'],
            ).run()
        except CatalogImageImportError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(result.preflight.render())
        self.stdout.write(result.render())
