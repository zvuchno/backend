"""Ротация ключей шифрования юридических данных."""

from django.core.management.base import BaseCommand

from common.encryption.providers import get_keyring

from users.services.legal_encryption_rotation import (
    LegalEncryptionRotationService,
)


class Command(BaseCommand):
    """Перешифровывает legal-данные активным ключом."""

    help = (
        'Перешифровывает юридические и банковские данные '
        'актуальным primary-ключом.'
    )

    def add_arguments(self, parser):
        """Добавляет параметры команды."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только проверить необходимость ротации.',
        )

    def handle(self, *args, **options):
        """Запускает ротацию encrypted-полей."""
        dry_run = options['dry_run']
        keyring = get_keyring()

        result = LegalEncryptionRotationService.rotate(
            dry_run=dry_run,
        )

        self.stdout.write(
            f'Активный ключ: {keyring.primary_key_id}',
        )
        self.stdout.write(
            f'Проверено значений: {result.checked}',
        )
        self.stdout.write(
            f'Требуют ротации: {result.outdated}',
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    'Dry run: данные не изменялись.',
                ),
            )
            return

        self.stdout.write(
            f'Перешифровано: {result.rotated}',
        )
        self.stdout.write(
            (
                'Пропущено из-за конкурентного изменения: '
                f'{result.concurrent_skips}'
            ),
        )
        self.stdout.write(
            self.style.SUCCESS(
                'Ротация завершена.',
            ),
        )
