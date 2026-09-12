"""Тесты ротации шифрования юридических данных."""

import pytest
from cryptography.fernet import Fernet
from django.db import connection
from django.db.models import Model

from common.encryption.keyring import (
    EncryptionKeyring,
    build_keyring,
)

from users.models import ArtistLegalProfile
from users.services.legal_encryption_rotation import (
    LegalEncryptionRotationService,
)

pytestmark = pytest.mark.django_db


def _make_keyrings() -> tuple[
    EncryptionKeyring,
    EncryptionKeyring,
]:
    """Создаёт старый и новый keyring для теста ротации."""
    old_key = Fernet.generate_key().decode('ascii')
    new_key = Fernet.generate_key().decode('ascii')

    old_keyring = build_keyring(
        primary_key_id='old-v1',
        raw_keys={
            'old-v1': old_key,
        },
    )
    new_keyring = build_keyring(
        primary_key_id='new-v2',
        raw_keys={
            'new-v2': new_key,
            'old-v1': old_key,
        },
    )

    return old_keyring, new_keyring


def _set_keyring(
    monkeypatch: pytest.MonkeyPatch,
    keyring: EncryptionKeyring,
) -> None:
    """Подменяет keyring для полей и сервиса ротации."""
    monkeypatch.setattr(
        'common.fields.encrypted.get_keyring',
        lambda: keyring,
    )
    monkeypatch.setattr(
        'users.services.legal_encryption_rotation.get_keyring',
        lambda: keyring,
    )


def _raw_field_value(
    model: type[Model],
    pk: object,
    field_name: str,
) -> str | None:
    """Читает ciphertext поля напрямую из БД."""
    table_name = connection.ops.quote_name(
        model._meta.db_table,
    )
    pk_column = connection.ops.quote_name(
        model._meta.pk.column,
    )
    field = model._meta.get_field(field_name)
    field_column = connection.ops.quote_name(
        field.column,
    )

    with connection.cursor() as cursor:
        cursor.execute(
            (
                f'SELECT {field_column} '
                f'FROM {table_name} '
                f'WHERE {pk_column} = %s'
            ),
            [pk],
        )
        return cursor.fetchone()[0]


def test_rotation_reencrypts_old_values_with_primary_key(
    artist_user,
    artist_legal_profile_factory,
    monkeypatch,
):
    """Старые значения перешифровываются актуальным ключом."""
    old_keyring, new_keyring = _make_keyrings()
    _set_keyring(
        monkeypatch,
        old_keyring,
    )

    legal_profile = artist_legal_profile_factory(
        user=artist_user,
    )
    identity = legal_profile.identity_data
    bank = legal_profile.bank_data

    ArtistLegalProfile.objects.filter(
        pk=legal_profile.pk,
    ).update(
        is_verified=True,
    )

    legal_profile.refresh_from_db()
    identity.refresh_from_db()
    bank.refresh_from_db()

    identity_inn = identity.inn
    bank_bik = bank.bik

    legal_updated_at = legal_profile.updated_at
    identity_updated_at = identity.updated_at
    bank_updated_at = bank.updated_at

    old_inn = _raw_field_value(
        type(identity),
        identity.pk,
        'inn',
    )
    old_bik = _raw_field_value(
        type(bank),
        bank.pk,
        'bik',
    )

    assert old_inn.startswith('zv1:old-v1:')
    assert old_bik.startswith('zv1:old-v1:')

    _set_keyring(
        monkeypatch,
        new_keyring,
    )

    result = LegalEncryptionRotationService.rotate()

    assert result.checked > 0
    assert result.outdated > 0
    assert result.rotated == result.outdated
    assert result.concurrent_skips == 0

    new_inn = _raw_field_value(
        type(identity),
        identity.pk,
        'inn',
    )
    new_bik = _raw_field_value(
        type(bank),
        bank.pk,
        'bik',
    )

    assert new_inn.startswith('zv1:new-v2:')
    assert new_bik.startswith('zv1:new-v2:')
    assert new_inn != old_inn
    assert new_bik != old_bik

    legal_profile.refresh_from_db()
    identity.refresh_from_db()
    bank.refresh_from_db()

    assert identity.inn == identity_inn
    assert bank.bik == bank_bik

    assert legal_profile.is_verified is True
    assert legal_profile.updated_at == legal_updated_at
    assert identity.updated_at == identity_updated_at
    assert bank.updated_at == bank_updated_at


def test_rotation_dry_run_does_not_modify_data(
    artist_user,
    artist_legal_profile_factory,
    monkeypatch,
):
    """Dry run находит старые ключи, но не меняет ciphertext."""
    old_keyring, new_keyring = _make_keyrings()
    _set_keyring(
        monkeypatch,
        old_keyring,
    )

    legal_profile = artist_legal_profile_factory(
        user=artist_user,
    )
    identity = legal_profile.identity_data

    old_inn = _raw_field_value(
        type(identity),
        identity.pk,
        'inn',
    )

    assert old_inn.startswith('zv1:old-v1:')

    _set_keyring(
        monkeypatch,
        new_keyring,
    )

    result = LegalEncryptionRotationService.rotate(
        dry_run=True,
    )

    assert result.checked > 0
    assert result.outdated > 0
    assert result.rotated == 0
    assert result.concurrent_skips == 0

    current_inn = _raw_field_value(
        type(identity),
        identity.pk,
        'inn',
    )

    assert current_inn == old_inn


def test_rotation_does_not_reencrypt_current_values(
    artist_user,
    artist_legal_profile_factory,
    monkeypatch,
):
    """Значения актуального ключа не переписываются."""
    _, new_keyring = _make_keyrings()
    _set_keyring(
        monkeypatch,
        new_keyring,
    )

    legal_profile = artist_legal_profile_factory(
        user=artist_user,
    )
    identity = legal_profile.identity_data

    old_inn = _raw_field_value(
        type(identity),
        identity.pk,
        'inn',
    )

    assert old_inn.startswith('zv1:new-v2:')

    result = LegalEncryptionRotationService.rotate()

    assert result.checked > 0
    assert result.outdated == 0
    assert result.rotated == 0
    assert result.concurrent_skips == 0

    current_inn = _raw_field_value(
        type(identity),
        identity.pk,
        'inn',
    )

    assert current_inn == old_inn
