"""Локальный источник ключей шифрования."""

import json
import os
from pathlib import Path

from common.encryption.exceptions import EncryptionConfigurationError
from common.encryption.keyring import EncryptionKeyring, build_keyring


def _load_from_file(path: str) -> EncryptionKeyring:
    """Загружает keyring из JSON-файла."""
    try:
        data = json.loads(
            Path(path).read_text(encoding='utf-8'),
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise EncryptionConfigurationError(
            'Не удалось загрузить keyring из файла.',
        ) from exc

    if not isinstance(data, dict):
        raise EncryptionConfigurationError(
            'Некорректный формат файла keyring.',
        )

    return build_keyring(
        primary_key_id=data.get('primary', ''),
        raw_keys=data.get('keys', {}),
    )


def _load_from_env() -> EncryptionKeyring:
    """Загружает keyring из переменных окружения."""
    primary_key_id = os.getenv(
        'FIELD_ENCRYPTION_PRIMARY_KEY_ID',
        '',
    ).strip()

    raw_value = os.getenv(
        'FIELD_ENCRYPTION_KEYS',
        '',
    ).strip()

    raw_keys = {}

    for item in filter(None, raw_value.split(',')):
        try:
            key_id, key = item.split(':', 1)
        except ValueError as exc:
            raise EncryptionConfigurationError(
                'Некорректный формат FIELD_ENCRYPTION_KEYS.',
            ) from exc

        key_id = key_id.strip()

        if key_id in raw_keys:
            raise EncryptionConfigurationError(
                f'Ключ {key_id!r} указан несколько раз.',
            )

        raw_keys[key_id] = key.strip()

    return build_keyring(
        primary_key_id=primary_key_id,
        raw_keys=raw_keys,
    )


def load_local_keyring() -> EncryptionKeyring:
    """Загружает локальный keyring."""
    keyring_file = os.getenv(
        'FIELD_ENCRYPTION_KEYRING_FILE',
        '',
    ).strip()

    if keyring_file:
        return _load_from_file(keyring_file)

    return _load_from_env()
