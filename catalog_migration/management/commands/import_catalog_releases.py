"""Команда разового импорта Album из bundle v1.3."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog_migration.services.catalog_release_import import (
    CatalogReleaseImportError,
    CatalogReleaseImporter,
)


class Command(BaseCommand):
    """Импортирует черновики Album после обязательного preflight."""

    help = 'Импортировать релизы migration-v1.3 в черновики Album'

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
            '--release-entity-id',
            help='Импортировать только указанный релиз внутри whitelist',
        )

    def handle(self, *args, **options):
        """Запускает импорт либо возвращает безопасную ошибку."""
        try:
            result = CatalogReleaseImporter(
                options['package_root'],
                dry_run=options['dry_run'],
                release_entity_id=options['release_entity_id'],
            ).run()
        except CatalogReleaseImportError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(result.preflight.render())
        self.stdout.write(result.render())
