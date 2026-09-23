"""Explicit, repeatable starter reference seeding (preview by default)."""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from catalog_migration.services.catalog_reference_seed import seed_references


class Command(BaseCommand):
    """Validate or create reference values required by the importer."""

    help = 'Проверить стартовые справочники; запись только с --apply'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            result = seed_references(apply=options['apply'])
        except ValidationError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(str(result))
