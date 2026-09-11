"""Тесты миграции шифрования юридических данных."""

from datetime import date
from importlib import import_module

import pytest
from cryptography.fernet import Fernet
from django.apps.registry import Apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from common.encryption.codec import decrypt_text
from common.encryption.keyring import build_keyring

from users.migrations.utils.legal_encryption_v1 import (
    decrypt_value,
    encrypt_value,
)

pytestmark = pytest.mark.django_db(transaction=True)

MIGRATE_FROM = (
    'users',
    '0030_alter_artistcontact_label_alter_artistsocial_label',
)
MIGRATE_TO = (
    'users',
    '0031_encrypt_legal_data',
)


def test_legal_encryption_v1_roundtrip():
    """Значение миграционного формата расшифровывается без потерь."""
    key = Fernet.generate_key().decode('ascii')
    keyring = build_keyring(
        primary_key_id='test-v1',
        raw_keys={
            'test-v1': key,
        },
    )

    plaintext = 'Иванов Иван, 1234 567890'

    encrypted = encrypt_value(
        plaintext,
        keyring,
    )

    assert encrypted.startswith('zv1:test-v1:')
    assert plaintext not in encrypted
    assert decrypt_value(encrypted, keyring) == plaintext


def test_legal_encryption_v1_is_runtime_compatible():
    """Миграционный ciphertext читается runtime-кодеком."""
    key = Fernet.generate_key().decode('ascii')
    keyring = build_keyring(
        primary_key_id='test-v1',
        raw_keys={
            'test-v1': key,
        },
    )

    plaintext = '40702810900000000001'

    encrypted = encrypt_value(
        plaintext,
        keyring,
    )

    assert (
        decrypt_text(
            encrypted,
            keyring=keyring,
        )
        == plaintext
    )


@pytest.fixture
def migration_keyring(monkeypatch):
    """Подменяет keyring для миграции и encrypted-полей."""
    key = Fernet.generate_key().decode('ascii')
    keyring = build_keyring(
        primary_key_id='test-v1',
        raw_keys={
            'test-v1': key,
        },
    )

    migration_module = import_module(
        'users.migrations.0031_encrypt_legal_data',
    )

    monkeypatch.setattr(
        migration_module,
        'get_keyring',
        lambda: keyring,
    )
    monkeypatch.setattr(
        'common.fields.encrypted.get_keyring',
        lambda: keyring,
    )

    return keyring


def _migrate(target) -> Apps:
    """Переводит test DB в указанное состояние users."""
    executor = MigrationExecutor(connection)
    executor.migrate([target])

    return executor.loader.project_state([target]).apps


def test_legal_data_encryption_migration_roundtrip(
    migration_keyring,
):
    """Миграция шифрует данные и полностью восстанавливает их."""
    old_apps = _migrate(MIGRATE_FROM)

    core_user_model = old_apps.get_model(
        'users',
        'CoreUser',
    )
    legal_profile_model = old_apps.get_model(
        'users',
        'ArtistLegalProfile',
    )
    identity_model = old_apps.get_model(
        'users',
        'ArtistIdentityData',
    )
    bank_model = old_apps.get_model(
        'users',
        'ArtistBankData',
    )

    user = core_user_model.objects.create(
        username='migration-user',
        email='migration@test.local',
        password='!',
    )
    legal_profile = legal_profile_model.objects.create(
        user_id=user.pk,
        email='migration@test.local',
        recipient_type='self_employed',
        is_verified=True,
    )

    identity = identity_model.objects.create(
        legal_profile_id=legal_profile.pk,
        first_name='Иван',
        last_name='Иванов',
        middle_name='Иванович',
        birth_date=date(1990, 1, 2),
        registration_address='г. Москва, ул. Тестовая, д. 1',
        passport_series='1234',
        passport_number='567890',
        passport_issued_by='Тестовый отдел МВД',
        passport_issue_date=date(2010, 2, 3),
        inn='123456789012',
    )
    bank = bank_model.objects.create(
        legal_profile_id=legal_profile.pk,
        bank_name='Тест-Банк',
        bik='123456789',
        correspondent_account='12345678901234567890',
        checking_account='09876543210987654321',
    )

    legal_updated_at = legal_profile.updated_at
    identity_updated_at = identity.updated_at
    bank_updated_at = bank.updated_at

    new_apps = _migrate(MIGRATE_TO)

    new_identity_model = new_apps.get_model(
        'users',
        'ArtistIdentityData',
    )
    new_bank_model = new_apps.get_model(
        'users',
        'ArtistBankData',
    )
    new_legal_profile_model = new_apps.get_model(
        'users',
        'ArtistLegalProfile',
    )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                first_name,
                last_name,
                birth_date,
                registration_address,
                passport_series,
                passport_number,
                passport_issued_by,
                passport_issue_date,
                inn
            FROM users_artistidentitydata
            WHERE id = %s
            """,
            [identity.pk],
        )
        raw_identity = cursor.fetchone()

        cursor.execute(
            """
            SELECT
                bank_name,
                bik,
                correspondent_account,
                checking_account
            FROM users_artistbankdata
            WHERE id = %s
            """,
            [bank.pk],
        )
        raw_bank = cursor.fetchone()

    # ФИО остаётся plaintext.
    assert raw_identity[0] == 'Иван'
    assert raw_identity[1] == 'Иванов'

    # Остальной identity-блок хранится encrypted.
    for value in raw_identity[2:]:
        assert value.startswith('zv1:test-v1:')

    # Весь bank-блок хранится encrypted.
    for value in raw_bank:
        assert value.startswith('zv1:test-v1:')

    new_identity = new_identity_model.objects.get(
        pk=identity.pk,
    )
    new_bank = new_bank_model.objects.get(
        pk=bank.pk,
    )
    new_legal_profile = new_legal_profile_model.objects.get(
        pk=legal_profile.pk,
    )

    # ORM возвращает исходные значения.
    assert new_identity.birth_date == date(1990, 1, 2)
    assert new_identity.registration_address == 'г. Москва, ул. Тестовая, д. 1'
    assert new_identity.passport_series == '1234'
    assert new_identity.passport_number == '567890'
    assert new_identity.passport_issued_by == 'Тестовый отдел МВД'
    assert new_identity.passport_issue_date == date(
        2010,
        2,
        3,
    )
    assert new_identity.inn == '123456789012'

    assert new_bank.bank_name == 'Тест-Банк'
    assert new_bank.bik == '123456789'
    assert new_bank.correspondent_account == '12345678901234567890'
    assert new_bank.checking_account == '09876543210987654321'

    # Техническая миграция не меняет бизнес-состояние.
    assert new_legal_profile.is_verified is True
    assert new_legal_profile.updated_at == legal_updated_at
    assert new_identity.updated_at == identity_updated_at
    assert new_bank.updated_at == bank_updated_at

    restored_apps = _migrate(MIGRATE_FROM)

    restored_identity_model = restored_apps.get_model(
        'users',
        'ArtistIdentityData',
    )
    restored_bank_model = restored_apps.get_model(
        'users',
        'ArtistBankData',
    )
    restored_legal_profile_model = restored_apps.get_model(
        'users',
        'ArtistLegalProfile',
    )

    restored_identity = restored_identity_model.objects.get(
        pk=identity.pk,
    )
    restored_bank = restored_bank_model.objects.get(
        pk=bank.pk,
    )
    restored_legal_profile = restored_legal_profile_model.objects.get(
        pk=legal_profile.pk,
    )

    assert restored_identity.birth_date == date(1990, 1, 2)
    assert (
        restored_identity.registration_address
        == 'г. Москва, ул. Тестовая, д. 1'
    )
    assert restored_identity.passport_series == '1234'
    assert restored_identity.passport_number == '567890'
    assert restored_identity.passport_issued_by == 'Тестовый отдел МВД'
    assert restored_identity.passport_issue_date == date(
        2010,
        2,
        3,
    )
    assert restored_identity.inn == '123456789012'

    assert restored_bank.bank_name == 'Тест-Банк'
    assert restored_bank.bik == '123456789'
    assert restored_bank.correspondent_account == '12345678901234567890'
    assert restored_bank.checking_account == '09876543210987654321'

    assert restored_legal_profile.is_verified is True
    assert restored_legal_profile.updated_at == legal_updated_at
    assert restored_identity.updated_at == identity_updated_at
    assert restored_bank.updated_at == bank_updated_at

    # Возвращаем test DB в актуальное состояние.
    _migrate(MIGRATE_TO)
