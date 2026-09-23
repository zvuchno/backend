"""Команда импорта цифровых Product и ProductVariant."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog_migration.services.catalog_digital_product_import import (
    CatalogDigitalProductImportError,
    CatalogDigitalProductImporter,
)


class Command(BaseCommand):
    """Создаёт коммерческую обвязку mapped Album и Track."""

    help = 'Импортировать цифровые товары Album и Track migration-v1.3'

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
            result = CatalogDigitalProductImporter(
                options['package_root'],
                dry_run=options['dry_run'],
            ).run()
        except CatalogDigitalProductImportError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(result.preflight.render())
        self.stdout.write(result.render())
