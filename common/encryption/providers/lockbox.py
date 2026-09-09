"""Получение keyring из Yandex Lockbox."""

import json
import os

import requests

from common.encryption.exceptions import EncryptionConfigurationError
from common.encryption.keyring import EncryptionKeyring, build_keyring

LOCKBOX_PAYLOAD_URL = (
    'https://payload.lockbox.api.cloud.yandex.net/'
    'lockbox/v1/secrets/{secret_id}/payload'
)

METADATA_TOKEN_URL = (
    'http://169.254.169.254/'
    'computeMetadata/v1/instance/'
    'service-accounts/default/token'
)

REQUEST_TIMEOUT = 5


def _get_explicit_iam_token() -> str | None:
    """Возвращает явно переданный IAM-токен."""
    return os.getenv('YANDEX_IAM_TOKEN', '').strip() or None


def _get_metadata_iam_token() -> str:
    """Получает IAM-токен сервисного аккаунта VM."""
    try:
        response = requests.get(
            METADATA_TOKEN_URL,
            headers={
                'Metadata-Flavor': 'Google',
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        token = response.json()['access_token']
    except (
        requests.RequestException,
        KeyError,
        ValueError,
    ) as exc:
        raise EncryptionConfigurationError(
            'Не удалось получить IAM-токен Yandex Cloud.',
        ) from exc

    return token


def _get_iam_token() -> str:
    """Возвращает доступный IAM-токен."""
    return _get_explicit_iam_token() or _get_metadata_iam_token()


def load_lockbox_keyring() -> EncryptionKeyring:
    """Загружает keyring из Yandex Lockbox."""
    secret_id = os.getenv(
        'YANDEX_LOCKBOX_SECRET_ID',
        '',
    ).strip()

    if not secret_id:
        raise EncryptionConfigurationError(
            'Не указан YANDEX_LOCKBOX_SECRET_ID.',
        )

    token = _get_iam_token()

    try:
        response = requests.get(
            LOCKBOX_PAYLOAD_URL.format(
                secret_id=secret_id,
            ),
            headers={
                'Authorization': f'Bearer {token}',
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (
        requests.RequestException,
        ValueError,
    ) as exc:
        raise EncryptionConfigurationError(
            'Не удалось получить keyring из Yandex Lockbox.',
        ) from exc

    entries = payload.get('entries', [])

    keyring_entry = next(
        (entry for entry in entries if entry.get('key') == 'keyring'),
        None,
    )

    if not keyring_entry:
        raise EncryptionConfigurationError(
            'В Lockbox отсутствует entry keyring.',
        )

    try:
        data = json.loads(keyring_entry['textValue'])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise EncryptionConfigurationError(
            'Некорректный keyring в Yandex Lockbox.',
        ) from exc

    if not isinstance(data, dict):
        raise EncryptionConfigurationError(
            'Некорректный формат keyring в Yandex Lockbox.',
        )

    return build_keyring(
        primary_key_id=data.get('primary', ''),
        raw_keys=data.get('keys', {}),
    )
