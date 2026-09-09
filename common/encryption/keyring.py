"""Работа с набором ключей шифрования."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet

from .exceptions import EncryptionConfigurationError


@dataclass(frozen=True)
class EncryptionKeyring:
    """Набор ключей шифрования с указанием активного ключа."""

    primary_key_id: str
    keys: dict[str, bytes]

    @property
    def primary_key(self) -> bytes:
        """Возвращает активный ключ шифрования."""
        return self.keys[self.primary_key_id]


def _validate_key(key_id: str, value: str) -> bytes:
    """Проверяет Fernet-ключ и возвращает его в байтовом виде."""
    key = value.encode('ascii')

    try:
        Fernet(key)
    except (ValueError, TypeError) as exc:
        raise EncryptionConfigurationError(
            f'Некорректный ключ шифрования {key_id!r}.',
        ) from exc

    return key


def _build_keyring(
    *,
    primary_key_id: str,
    raw_keys: dict[str, str],
) -> EncryptionKeyring:
    """Создаёт и проверяет keyring."""
    if not primary_key_id:
        raise EncryptionConfigurationError(
            'Не указан primary key id.',
        )

    if primary_key_id not in raw_keys:
        raise EncryptionConfigurationError(
            'Активный ключ отсутствует в keyring.',
        )

    keys = {
        key_id: _validate_key(key_id, value)
        for key_id, value in raw_keys.items()
    }

    return EncryptionKeyring(
        primary_key_id=primary_key_id,
        keys=keys,
    )


def _load_from_file(path: str) -> EncryptionKeyring:
    """Загружает keyring из JSON-файла."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise EncryptionConfigurationError(
            'Не удалось загрузить keyring из файла.',
        ) from exc

    return _build_keyring(
        primary_key_id=data.get('primary', ''),
        raw_keys=data.get('keys', {}),
    )


def _load_from_env() -> EncryptionKeyring:
    """Загружает keyring из переменных окружения."""
    primary_key_id = os.getenv(
        'FIELD_ENCRYPTION_PRIMARY_KEY_ID',
        '',
    ).strip()
    raw_value = os.getenv('FIELD_ENCRYPTION_KEYS', '').strip()

    raw_keys = {}

    for item in filter(None, raw_value.split(',')):
        try:
            key_id, key = item.split(':', 1)
        except ValueError as exc:
            raise EncryptionConfigurationError(
                'Некорректный формат FIELD_ENCRYPTION_KEYS.',
            ) from exc

        raw_keys[key_id.strip()] = key.strip()

    return _build_keyring(
        primary_key_id=primary_key_id,
        raw_keys=raw_keys,
    )


def load_keyring() -> EncryptionKeyring:
    """Загружает keyring из настроенного источника."""
    keyring_file = os.getenv(
        'FIELD_ENCRYPTION_KEYRING_FILE',
        '',
    ).strip()

    if keyring_file:
        return _load_from_file(keyring_file)

    return _load_from_env()
