"""Команда импорта дополнительных данных mapped-профилей."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog_migration.services.catalog_profile_extras_import import (
    CatalogProfileExtrasImportError,
    CatalogProfileExtrasImporter,
)


class Command(BaseCommand):
    """Импортирует контакты, Telegram и неподтверждённые точки СДЭК."""

    help = 'Импортировать дополнительные данные профилей migration-v1.3'

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
            result = CatalogProfileExtrasImporter(
                options['package_root'],
                dry_run=options['dry_run'],
            ).run()
        except CatalogProfileExtrasImportError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(result.preflight.render())
        self.stdout.write(result.render())
