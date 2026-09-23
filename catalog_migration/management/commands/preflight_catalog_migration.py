"""Команда read-only preflight пакета миграции каталога."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog_migration.services.catalog_migration_preflight import (
    CatalogMigrationPreflight,
)


class Command(BaseCommand):
    """Проверяет локальный пакет migration-v1.3."""

    help = 'Проверить пакет migration-v1.3 без запуска импорта'

    def add_arguments(self, parser):
        """Добавляет путь к корню пакета."""
        parser.add_argument(
            'package_root',
            type=Path,
            help='Каталог с bundle и конфигурационными JSON',
        )

    def handle(self, *args, **options):
        """Запускает preflight и возвращает ненулевой код при ошибках."""
        result = CatalogMigrationPreflight(options['package_root']).run()
        self.stdout.write(result.render())
        if not result.passed:
            raise CommandError(
                f'Preflight завершился с ошибками: {len(result.errors)}',
            )
