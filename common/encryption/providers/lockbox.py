"""Получение keyring из Yandex Lockbox."""

import json
import os

import yandexcloud
from yandex.cloud.lockbox.v1.payload_service_pb2 import (
    GetPayloadRequest,
)
from yandex.cloud.lockbox.v1.payload_service_pb2_grpc import (
    PayloadServiceStub,
)

from common.encryption.exceptions import EncryptionConfigurationError
from common.encryption.keyring import EncryptionKeyring, build_keyring


def _get_sdk() -> yandexcloud.SDK:
    """Создаёт SDK с доступным способом аутентификации."""
    iam_token = os.getenv(
        'YANDEX_IAM_TOKEN',
        '',
    ).strip()

    if iam_token:
        return yandexcloud.SDK(
            iam_token=iam_token,
        )

    return yandexcloud.SDK()


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

    try:
        sdk = _get_sdk()

        client = sdk.client(
            PayloadServiceStub,
        )

        payload = client.Get(
            GetPayloadRequest(
                secret_id=secret_id,
            ),
        )
    except Exception as exc:
        raise EncryptionConfigurationError(
            'Не удалось получить keyring из Yandex Lockbox.',
        ) from exc

    keyring_entry = next(
        (entry for entry in payload.entries if entry.key == 'keyring'),
        None,
    )

    if keyring_entry is None:
        raise EncryptionConfigurationError(
            'В Lockbox отсутствует entry keyring.',
        )

    try:
        data = json.loads(
            keyring_entry.text_value,
        )
    except (TypeError, json.JSONDecodeError) as exc:
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
