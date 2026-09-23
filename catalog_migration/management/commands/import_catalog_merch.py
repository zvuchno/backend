"""Команда разового импорта мерча и его торговых предложений."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog_migration.services.catalog_merch_import import (
    CatalogMerchImportError,
    CatalogMerchImporter,
)


class Command(BaseCommand):
    """Импортирует Merch, Product и ProductVariant после preflight."""

    help = 'Импортировать мерч migration-v1.3 без изображений'

    def add_arguments(self, parser):
        parser.add_argument(
            'package_root',
            type=Path,
            help='Каталог с bundle и конфигурационными JSON',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Выполнить preflight и проверки БД без записи',
        )

    def handle(self, *args, **options):
        try:
            result = CatalogMerchImporter(
                options['package_root'],
                dry_run=options['dry_run'],
            ).run()
        except CatalogMerchImportError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(result.preflight.render())
        self.stdout.write(result.render())
