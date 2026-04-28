"""Генерация ключа для шифрования полей."""

from cryptography.fernet import Fernet
from django.core.management import BaseCommand


class Command(BaseCommand):
    """Генерирует Fernet-ключ для FIELD_ENCRYPTION_KEYS."""

    help = 'Генерирует ключ для добавления в env.'

    def handle(self, *args, **options):
        key = Fernet.generate_key().decode()
        self.stdout.write(
            self.style.SUCCESS(
                'Скопируйте и добавьте в .env в FIELD_ENCRYPTION_KEYS\n'
                f'{key}\n'
                'Если ключей несколько — новый должен быть первым (ротация).',
            ),
        )
