"""Поля моделей с шифрованием значений."""

from django.db import models

from common.encryption.codec import decrypt_text, encrypt_text
from common.encryption.providers import get_keyring


class EncryptedCharField(models.CharField):
    """Строковое поле с шифрованием непустого значения."""

    def db_type(self, connection):
        """Хранит ciphertext в текстовой колонке без ограничения длины."""
        return models.TextField().db_type(connection)

    def get_prep_value(self, value):
        """Подготавливает значение к сохранению в БД."""
        value = super().get_prep_value(value)

        if value is None or value == '':
            return value

        return encrypt_text(
            value,
            keyring=get_keyring(),
        )

    def from_db_value(self, value, expression, connection):
        """Расшифровывает значение, полученное из БД."""
        if value is None or value == '':
            return value

        return decrypt_text(
            value,
            keyring=get_keyring(),
        )


class EncryptedDateField(models.DateField):
    """Поле даты с хранением значения в зашифрованном виде."""

    def db_type(self, connection):
        """Хранит ciphertext в текстовой колонке."""
        return models.TextField().db_type(connection)

    def get_prep_value(self, value):
        """Преобразует дату в ISO-формат и шифрует."""
        value = super().get_prep_value(value)

        if value is None:
            return None

        return encrypt_text(
            value.isoformat(),
            keyring=get_keyring(),
        )

    def get_db_prep_value(
        self,
        value,
        connection,
        prepared=False,
    ):
        """Возвращает ciphertext без адаптации как SQL DATE."""
        if not prepared:
            value = self.get_prep_value(value)

        return value

    def from_db_value(self, value, expression, connection):
        """Расшифровывает дату, полученную из БД."""
        if value is None:
            return None

        plaintext = decrypt_text(
            value,
            keyring=get_keyring(),
        )

        return super().to_python(plaintext)
