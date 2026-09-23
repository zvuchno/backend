"""Команда разового импорта профилей из bundle v1.3."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog_migration.services.catalog_profile_import import (
    CatalogProfileImportError,
    CatalogProfileImporter,
)


class Command(BaseCommand):
    """Импортирует ArtistProfile после обязательного preflight."""

    help = 'Импортировать профили migration-v1.3 в черновики'

    def add_arguments(self, parser):
        """Добавляет путь к пакету и безопасный пробный режим."""
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
        """Запускает импорт либо возвращает безопасную ошибку."""
        try:
            result = CatalogProfileImporter(
                options['package_root'],
                dry_run=options['dry_run'],
            ).run()
        except CatalogProfileImportError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(result.preflight.render())
        self.stdout.write(result.render())
