"""Формат шифрования legal-данных для миграций."""

from cryptography.fernet import Fernet, InvalidToken

FORMAT_VERSION = 'zv1'
SEPARATOR = ':'


def encrypt_value(value: str, keyring) -> str:
    """Шифрует строку в формате zv1."""
    token = Fernet(
        keyring.primary_key,
    ).encrypt(
        value.encode('utf-8'),
    )

    return SEPARATOR.join(
        (
            FORMAT_VERSION,
            keyring.primary_key_id,
            token.decode('ascii'),
        ),
    )


def decrypt_value(value: str, keyring) -> str:
    """Расшифровывает значение формата zv1."""
    parts = value.split(SEPARATOR, 2)

    if len(parts) != 3:
        raise RuntimeError(
            'Некорректный формат зашифрованного значения.',
        )

    version, key_id, token = parts

    if version != FORMAT_VERSION:
        raise RuntimeError(
            f'Неподдерживаемый формат шифрования: {version}.',
        )

    key = keyring.keys.get(key_id)

    if key is None:
        raise RuntimeError(
            f'Ключ шифрования {key_id} отсутствует в keyring.',
        )

    try:
        plaintext = Fernet(key).decrypt(
            token.encode('ascii'),
        )
        return plaintext.decode('utf-8')
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise RuntimeError(
            'Не удалось расшифровать значение.',
        ) from exc
