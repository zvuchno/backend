"""Генерация ключа для шифрования полей."""

from cryptography.fernet import Fernet
from django.core.management import BaseCommand


class Command(BaseCommand):
    """Генерирует Fernet-ключ для FIELD_ENCRYPTION_KEYS."""

    help = 'Генерирует ключ для добавления в env.'

    def handle(self, *args, **options):
        key = Fernet.generate_key().decode()
        self.stdout.write(
            self.style.SUCCESS(f'FIELD_ENCRYPTION_KEYS={key}'),
        )
