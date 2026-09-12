"""Генерация ключа шифрования."""

from cryptography.fernet import Fernet
from django.core.management import BaseCommand


class Command(BaseCommand):
    """Генерирует новый Fernet-ключ."""

    help = 'Генерирует Fernet-ключ для шифрования полей.'

    def handle(self, *args, **options):
        self.stdout.write(
            Fernet.generate_key().decode('ascii'),
        )
