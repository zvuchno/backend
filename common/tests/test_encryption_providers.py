"""Тесты источников ключей шифрования."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet

from common.encryption.exceptions import EncryptionConfigurationError
from common.encryption.providers.local import load_local_keyring
from common.encryption.providers.lockbox import (
    _get_sdk,
    load_lockbox_keyring,
)
from common.encryption.providers.selector import load_keyring


def generate_key() -> str:
    """Генерирует Fernet-ключ для тестов."""
    return Fernet.generate_key().decode('ascii')


def test_local_provider_loads_keys_from_env(monkeypatch):
    """Локальный provider загружает keyring из env."""
    current_key = generate_key()
    old_key = generate_key()

    monkeypatch.delenv(
        'FIELD_ENCRYPTION_KEYRING_FILE',
        raising=False,
    )
    monkeypatch.setenv(
        'FIELD_ENCRYPTION_PRIMARY_KEY_ID',
        'current',
    )
    monkeypatch.setenv(
        'FIELD_ENCRYPTION_KEYS',
        f'current:{current_key},old:{old_key}',
    )

    keyring = load_local_keyring()

    assert keyring.primary_key_id == 'current'
    assert keyring.keys == {
        'current': current_key.encode('ascii'),
        'old': old_key.encode('ascii'),
    }


def test_local_provider_prefers_file(monkeypatch, tmp_path):
    """Файл keyring имеет приоритет над env."""
    file_key = generate_key()
    env_key = generate_key()

    keyring_file = tmp_path / 'keyring.json'
    keyring_file.write_text(
        json.dumps(
            {
                'primary': 'file-key',
                'keys': {
                    'file-key': file_key,
                },
            },
        ),
        encoding='utf-8',
    )

    monkeypatch.setenv(
        'FIELD_ENCRYPTION_KEYRING_FILE',
        str(keyring_file),
    )
    monkeypatch.setenv(
        'FIELD_ENCRYPTION_PRIMARY_KEY_ID',
        'env-key',
    )
    monkeypatch.setenv(
        'FIELD_ENCRYPTION_KEYS',
        f'env-key:{env_key}',
    )

    keyring = load_local_keyring()

    assert keyring.primary_key_id == 'file-key'
    assert keyring.keys == {
        'file-key': file_key.encode('ascii'),
    }


def test_local_provider_rejects_duplicate_keys(monkeypatch):
    """Одинаковый идентификатор нельзя указать дважды."""
    first_key = generate_key()
    second_key = generate_key()

    monkeypatch.delenv(
        'FIELD_ENCRYPTION_KEYRING_FILE',
        raising=False,
    )
    monkeypatch.setenv(
        'FIELD_ENCRYPTION_PRIMARY_KEY_ID',
        'duplicate',
    )
    monkeypatch.setenv(
        'FIELD_ENCRYPTION_KEYS',
        (f'duplicate:{first_key},duplicate:{second_key}'),
    )

    with pytest.raises(EncryptionConfigurationError):
        load_local_keyring()


def test_sdk_uses_explicit_iam_token(monkeypatch):
    """SDK использует явно переданный IAM-токен."""
    monkeypatch.setenv(
        'YANDEX_IAM_TOKEN',
        'test-token',
    )

    sdk_mock = Mock()
    monkeypatch.setattr(
        'common.encryption.providers.lockbox.yandexcloud.SDK',
        sdk_mock,
    )

    _get_sdk()

    sdk_mock.assert_called_once_with(
        iam_token='test-token',
    )


def test_sdk_uses_metadata_without_explicit_token(monkeypatch):
    """Без явного токена SDK использует metadata-аутентификацию."""
    monkeypatch.delenv(
        'YANDEX_IAM_TOKEN',
        raising=False,
    )

    sdk_mock = Mock()
    monkeypatch.setattr(
        'common.encryption.providers.lockbox.yandexcloud.SDK',
        sdk_mock,
    )

    _get_sdk()

    sdk_mock.assert_called_once_with()


def test_lockbox_provider_loads_keyring(monkeypatch):
    """Lockbox provider разбирает keyring из payload."""
    encryption_key = generate_key()

    monkeypatch.setenv(
        'YANDEX_LOCKBOX_SECRET_ID',
        'test-secret',
    )

    payload = SimpleNamespace(
        entries=[
            SimpleNamespace(
                key='keyring',
                text_value=json.dumps(
                    {
                        'primary': 'cloud-v1',
                        'keys': {
                            'cloud-v1': encryption_key,
                        },
                    },
                ),
            ),
        ],
    )

    client = Mock()
    client.Get.return_value = payload

    sdk = Mock()
    sdk.client.return_value = client

    monkeypatch.setattr(
        'common.encryption.providers.lockbox._get_sdk',
        Mock(return_value=sdk),
    )

    keyring = load_lockbox_keyring()

    assert keyring.primary_key_id == 'cloud-v1'
    assert keyring.keys == {
        'cloud-v1': encryption_key.encode('ascii'),
    }

    sdk.client.assert_called_once()


def test_lockbox_provider_requires_keyring_entry(monkeypatch):
    """В Lockbox должен присутствовать entry keyring."""
    monkeypatch.setenv(
        'YANDEX_LOCKBOX_SECRET_ID',
        'test-secret',
    )

    payload = SimpleNamespace(
        entries=[],
    )

    client = Mock()
    client.Get.return_value = payload

    sdk = Mock()
    sdk.client.return_value = client

    monkeypatch.setattr(
        'common.encryption.providers.lockbox._get_sdk',
        Mock(return_value=sdk),
    )

    with pytest.raises(
        EncryptionConfigurationError,
        match='отсутствует entry keyring',
    ):
        load_lockbox_keyring()


def test_auto_uses_local_without_lockbox(monkeypatch):
    """Auto использует local, если Lockbox не настроен."""
    local_key = generate_key()

    monkeypatch.setenv(
        'FIELD_ENCRYPTION_KEY_SOURCE',
        'auto',
    )
    monkeypatch.delenv(
        'YANDEX_LOCKBOX_SECRET_ID',
        raising=False,
    )
    monkeypatch.delenv(
        'FIELD_ENCRYPTION_KEYRING_FILE',
        raising=False,
    )
    monkeypatch.setenv(
        'FIELD_ENCRYPTION_PRIMARY_KEY_ID',
        'local-v1',
    )
    monkeypatch.setenv(
        'FIELD_ENCRYPTION_KEYS',
        f'local-v1:{local_key}',
    )

    keyring = load_keyring()

    assert keyring.primary_key_id == 'local-v1'


def test_auto_uses_lockbox_when_configured(monkeypatch):
    """Auto выбирает Lockbox при наличии secret ID."""
    expected = object()

    monkeypatch.setenv(
        'FIELD_ENCRYPTION_KEY_SOURCE',
        'auto',
    )
    monkeypatch.setenv(
        'YANDEX_LOCKBOX_SECRET_ID',
        'test-secret',
    )

    lockbox_mock = Mock(return_value=expected)

    monkeypatch.setattr(
        ('common.encryption.providers.selector.load_lockbox_keyring'),
        lockbox_mock,
    )

    result = load_keyring()

    assert result is expected
    lockbox_mock.assert_called_once_with()


def test_auto_does_not_fallback_when_lockbox_fails(
    monkeypatch,
):
    """Ошибка настроенного Lockbox не приводит к local fallback."""
    monkeypatch.setenv(
        'FIELD_ENCRYPTION_KEY_SOURCE',
        'auto',
    )
    monkeypatch.setenv(
        'YANDEX_LOCKBOX_SECRET_ID',
        'test-secret',
    )

    lockbox_mock = Mock(
        side_effect=EncryptionConfigurationError(
            'Lockbox unavailable.',
        ),
    )
    local_mock = Mock()

    monkeypatch.setattr(
        ('common.encryption.providers.selector.load_lockbox_keyring'),
        lockbox_mock,
    )
    monkeypatch.setattr(
        ('common.encryption.providers.selector.load_local_keyring'),
        local_mock,
    )

    with pytest.raises(
        EncryptionConfigurationError,
        match='Lockbox unavailable',
    ):
        load_keyring()

    lockbox_mock.assert_called_once_with()
    local_mock.assert_not_called()


def test_unknown_key_source_fails(monkeypatch):
    """Неизвестный источник ключей считается ошибкой."""
    monkeypatch.setenv(
        'FIELD_ENCRYPTION_KEY_SOURCE',
        'unknown',
    )

    with pytest.raises(
        EncryptionConfigurationError,
        match='Неизвестный источник ключей',
    ):
        load_keyring()
