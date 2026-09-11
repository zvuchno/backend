"""Тесты зашифрованных полей моделей."""

from datetime import date

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError
from django.db import connection, models

from common.encryption.keyring import build_keyring
from common.fields import EncryptedCharField, EncryptedDateField

pytestmark = pytest.mark.django_db(transaction=True)


class EncryptedFieldsTestModel(models.Model):
    """Тестовая модель зашифрованных полей."""

    secret = EncryptedCharField(
        max_length=20,
        blank=True,
    )
    secret_date = EncryptedDateField(
        blank=True,
        null=True,
    )

    class Meta:
        app_label = 'common'
        db_table = 'common_test_encrypted_fields'


@pytest.fixture
def encrypted_model(transactional_db):
    """Создаёт временную таблицу для тестов полей."""
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(EncryptedFieldsTestModel)

    try:
        yield EncryptedFieldsTestModel
    finally:
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(EncryptedFieldsTestModel)


@pytest.fixture(scope='module')
def encrypted_model(django_db_setup, django_db_blocker):
    """Создаёт временную таблицу для тестов полей."""
    table_name = EncryptedFieldsTestModel._meta.db_table

    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            cursor.execute(
                f'DROP TABLE IF EXISTS "{table_name}" CASCADE',
            )

        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(
                EncryptedFieldsTestModel,
            )

    yield EncryptedFieldsTestModel

    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            cursor.execute(
                f'DROP TABLE IF EXISTS "{table_name}" CASCADE',
            )


@pytest.fixture
def encryption_keyring(monkeypatch):
    """Подменяет источник ключей тестовым keyring."""
    key = Fernet.generate_key().decode('ascii')

    keyring = build_keyring(
        primary_key_id='test-v1',
        raw_keys={
            'test-v1': key,
        },
    )

    monkeypatch.setattr(
        'common.fields.encrypted.get_keyring',
        lambda: keyring,
    )

    return keyring


def test_encrypted_char_field_roundtrip(
    encrypted_model,
    encryption_keyring,
):
    """Строка хранится зашифрованной и читается открытой."""
    plaintext = 'Иван Иванов'

    obj = encrypted_model.objects.create(
        secret=plaintext,
    )

    with connection.cursor() as cursor:
        cursor.execute(
            ('SELECT secret FROM common_test_encrypted_fields WHERE id = %s'),
            [obj.pk],
        )
        raw_value = cursor.fetchone()[0]

    assert raw_value.startswith('zv1:test-v1:')
    assert plaintext not in raw_value

    obj = encrypted_model.objects.get(pk=obj.pk)

    assert obj.secret == plaintext


def test_encrypted_date_field_roundtrip(
    encrypted_model,
    encryption_keyring,
):
    """Дата хранится зашифрованной и читается как date."""
    value = date(1990, 1, 2)

    obj = encrypted_model.objects.create(
        secret_date=value,
    )

    with connection.cursor() as cursor:
        cursor.execute(
            (
                'SELECT secret_date '
                'FROM common_test_encrypted_fields '
                'WHERE id = %s'
            ),
            [obj.pk],
        )
        raw_value = cursor.fetchone()[0]

    assert raw_value.startswith('zv1:test-v1:')
    assert '1990-01-02' not in raw_value

    obj = encrypted_model.objects.get(pk=obj.pk)

    assert obj.secret_date == value
    assert isinstance(obj.secret_date, date)


def test_empty_values_are_not_encrypted(
    encrypted_model,
    encryption_keyring,
):
    """Пустые значения сохраняют существующую семантику БД."""
    obj = encrypted_model.objects.create(
        secret='',
        secret_date=None,
    )

    with connection.cursor() as cursor:
        cursor.execute(
            (
                'SELECT secret, secret_date '
                'FROM common_test_encrypted_fields '
                'WHERE id = %s'
            ),
            [obj.pk],
        )
        raw_secret, raw_date = cursor.fetchone()

    assert raw_secret == ''
    assert raw_date is None

    obj = encrypted_model.objects.get(pk=obj.pk)

    assert obj.secret == ''
    assert obj.secret_date is None


def test_char_field_preserves_max_length_validation(
    encrypted_model,
    encryption_keyring,
):
    """max_length проверяет plaintext, а не ciphertext."""
    obj = encrypted_model(
        secret='x' * 21,
    )

    with pytest.raises(ValidationError):
        obj.full_clean()


def test_encrypted_char_empty_lookup(
    encrypted_model,
    encryption_keyring,
):
    """Проверка на непустое значение работает через сравнение с ''."""
    empty = encrypted_model.objects.create(
        secret='',
    )
    filled = encrypted_model.objects.create(
        secret='value',
    )

    queryset = encrypted_model.objects.filter(
        secret__gt='',
    )

    assert list(queryset.values_list('pk', flat=True)) == [
        filled.pk,
    ]
    assert empty.pk not in queryset


def test_encrypted_date_isnull_lookup(
    encrypted_model,
    encryption_keyring,
):
    """Isnull продолжает работать для зашифрованной даты."""
    empty = encrypted_model.objects.create(
        secret_date=None,
    )
    filled = encrypted_model.objects.create(
        secret_date=date(1990, 1, 2),
    )

    queryset = encrypted_model.objects.filter(
        secret_date__isnull=False,
    )

    assert list(queryset.values_list('pk', flat=True)) == [
        filled.pk,
    ]
    assert empty.pk not in queryset


def test_encrypted_char_exact_plaintext_lookup_does_not_match(
    encrypted_model,
    encryption_keyring,
):
    """Поиск encrypted-поля по plaintext не поддерживается."""
    encrypted_model.objects.create(
        secret='value',
    )

    assert not encrypted_model.objects.filter(
        secret='value',
    ).exists()
