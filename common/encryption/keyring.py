"""Набор ключей шифрования."""

import re
from dataclasses import dataclass
from typing import Mapping

from cryptography.fernet import Fernet

from .exceptions import EncryptionConfigurationError

KEY_ID_PATTERN = re.compile(r'^[A-Za-z0-9._-]{1,64}$')


@dataclass(frozen=True)
class EncryptionKeyring:
    """Набор ключей шифрования с указанием активного ключа."""

    primary_key_id: str
    keys: dict[str, bytes]

    @property
    def primary_key(self) -> bytes:
        """Возвращает активный ключ шифрования."""
        return self.keys[self.primary_key_id]


def _validate_key_id(key_id: str) -> None:
    """Проверяет идентификатор ключа."""
    if not KEY_ID_PATTERN.fullmatch(key_id):
        raise EncryptionConfigurationError(
            f'Некорректный идентификатор ключа {key_id!r}.',
        )


def _validate_key(key_id: str, value: str) -> bytes:
    """Проверяет Fernet-ключ."""
    if not isinstance(value, str):
        raise EncryptionConfigurationError(
            f'Ключ {key_id!r} должен быть строкой.',
        )

    try:
        key = value.encode('ascii')
        Fernet(key)
    except (UnicodeEncodeError, ValueError, TypeError) as exc:
        raise EncryptionConfigurationError(
            f'Некорректный ключ шифрования {key_id!r}.',
        ) from exc

    return key


def build_keyring(
    *,
    primary_key_id: str,
    raw_keys: Mapping[str, str],
) -> EncryptionKeyring:
    """Создаёт и проверяет keyring."""
    if not primary_key_id:
        raise EncryptionConfigurationError(
            'Не указан активный ключ шифрования.',
        )

    if not raw_keys:
        raise EncryptionConfigurationError(
            'Keyring не содержит ключей.',
        )

    _validate_key_id(primary_key_id)

    keys = {}

    for key_id, value in raw_keys.items():
        _validate_key_id(key_id)
        keys[key_id] = _validate_key(key_id, value)

    if primary_key_id not in keys:
        raise EncryptionConfigurationError(
            'Активный ключ отсутствует в keyring.',
        )

    return EncryptionKeyring(
        primary_key_id=primary_key_id,
        keys=keys,
    )
