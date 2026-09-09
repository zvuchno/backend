"""Кодирование и декодирование зашифрованных значений."""

from cryptography.fernet import Fernet, InvalidToken

from .exceptions import (
    EncryptionKeyNotFoundError,
    InvalidEncryptedValueError,
)
from .keyring import EncryptionKeyring

FORMAT_VERSION = 'zv1'
SEPARATOR = ':'


def encrypt_text(
    value: str,
    *,
    keyring: EncryptionKeyring,
) -> str:
    """Шифрует строку активным ключом."""
    token = (
        Fernet(
            keyring.primary_key,
        )
        .encrypt(
            value.encode('utf-8'),
        )
        .decode('ascii')
    )

    return SEPARATOR.join(
        (
            FORMAT_VERSION,
            keyring.primary_key_id,
            token,
        ),
    )


def decrypt_text(
    value: str,
    *,
    keyring: EncryptionKeyring,
) -> str:
    """Расшифровывает значение соответствующим ключом."""
    parts = value.split(SEPARATOR, 2)

    if len(parts) != 3 or parts[0] != FORMAT_VERSION:
        raise InvalidEncryptedValueError(
            'Неизвестный формат зашифрованного значения.',
        )

    _, key_id, token = parts

    key = keyring.keys.get(key_id)
    if key is None:
        raise EncryptionKeyNotFoundError(
            f'Не найден ключ шифрования {key_id!r}.',
        )

    try:
        plaintext = Fernet(key).decrypt(
            token.encode('ascii'),
        )
    except InvalidToken as exc:
        raise InvalidEncryptedValueError(
            'Не удалось расшифровать значение.',
        ) from exc

    try:
        return plaintext.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise InvalidEncryptedValueError(
            'Расшифрованное значение имеет некорректный формат.',
        ) from exc


def needs_rotation(
    value: str,
    *,
    keyring: EncryptionKeyring,
) -> bool:
    """Проверяет, зашифровано ли значение устаревшим ключом."""
    parts = value.split(SEPARATOR, 2)

    if len(parts) != 3 or parts[0] != FORMAT_VERSION:
        raise InvalidEncryptedValueError(
            'Неизвестный формат зашифрованного значения.',
        )

    return parts[1] != keyring.primary_key_id
