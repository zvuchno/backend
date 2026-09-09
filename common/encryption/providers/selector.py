"""Выбор источника ключей шифрования."""

import os

from common.encryption.exceptions import EncryptionConfigurationError
from common.encryption.keyring import EncryptionKeyring

from .local import load_local_keyring
from .lockbox import load_lockbox_keyring

SUPPORTED_SOURCES = {
    'auto',
    'local',
    'lockbox',
}


def load_keyring() -> EncryptionKeyring:
    """Загружает keyring из настроенного источника."""
    source = (
        os
        .getenv(
            'FIELD_ENCRYPTION_KEY_SOURCE',
            'auto',
        )
        .strip()
        .lower()
    )

    if source not in SUPPORTED_SOURCES:
        raise EncryptionConfigurationError(
            f'Неизвестный источник ключей {source!r}.',
        )

    if source == 'local':
        return load_local_keyring()

    if source == 'lockbox':
        return load_lockbox_keyring()

    lockbox_secret_id = os.getenv(
        'YANDEX_LOCKBOX_SECRET_ID',
        '',
    ).strip()

    if lockbox_secret_id:
        return load_lockbox_keyring()

    return load_local_keyring()
