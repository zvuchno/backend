"""Команда разового импорта метаданных Track из bundle v1.3."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog_migration.services.catalog_track_import import (
    CatalogTrackImportError,
    CatalogTrackImporter,
)


class Command(BaseCommand):
    """Импортирует Track без аудио после обязательного preflight."""

    help = 'Импортировать метаданные Track migration-v1.3'

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
        parser.add_argument(
            '--track-entity-id',
            help='Импортировать только указанный трек внутри whitelist',
        )

    def handle(self, *args, **options):
        """Запускает импорт либо возвращает безопасную ошибку."""
        try:
            result = CatalogTrackImporter(
                options['package_root'],
                dry_run=options['dry_run'],
                track_entity_id=options['track_entity_id'],
            ).run()
        except CatalogTrackImportError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(result.preflight.render())
        self.stdout.write(result.render())
