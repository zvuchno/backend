"""Тесты базового механизма шифрования."""

import pytest
from cryptography.fernet import Fernet

from common.encryption.codec import (
    decrypt_text,
    encrypt_text,
    needs_rotation,
)
from common.encryption.exceptions import (
    EncryptionConfigurationError,
    EncryptionKeyNotFoundError,
    InvalidEncryptedValueError,
)
from common.encryption.keyring import build_keyring


def generate_key() -> str:
    """Генерирует Fernet-ключ для тестов."""
    return Fernet.generate_key().decode('ascii')


def make_keyring(
    *,
    primary='key-v1',
    keys=None,
):
    """Создаёт тестовый keyring."""
    keys = keys or {
        primary: generate_key(),
    }

    return build_keyring(
        primary_key_id=primary,
        raw_keys=keys,
    )


def test_encrypt_and_decrypt_text():
    """Шифрование и расшифровка сохраняют исходное значение."""
    keyring = make_keyring()
    plaintext = 'Иванов Иван Иванович'

    encrypted = encrypt_text(
        plaintext,
        keyring=keyring,
    )

    assert (
        decrypt_text(
            encrypted,
            keyring=keyring,
        )
        == plaintext
    )


def test_encrypted_value_does_not_contain_plaintext():
    """Зашифрованное значение не содержит исходный текст."""
    keyring = make_keyring()
    plaintext = '1234 567890'

    encrypted = encrypt_text(
        plaintext,
        keyring=keyring,
    )

    assert plaintext not in encrypted


def test_encrypt_uses_primary_key_id():
    """Новое значение содержит идентификатор активного ключа."""
    keyring = make_keyring(
        primary='key-2026',
    )

    encrypted = encrypt_text(
        'секрет',
        keyring=keyring,
    )

    assert encrypted.startswith('zv1:key-2026:')


def test_old_key_can_decrypt_after_rotation():
    """Старый ключ остаётся пригодным для расшифровки."""
    old_key = generate_key()
    new_key = generate_key()

    old_keyring = make_keyring(
        primary='key-old',
        keys={
            'key-old': old_key,
        },
    )
    encrypted = encrypt_text(
        'старое значение',
        keyring=old_keyring,
    )

    rotated_keyring = make_keyring(
        primary='key-new',
        keys={
            'key-new': new_key,
            'key-old': old_key,
        },
    )

    assert (
        decrypt_text(
            encrypted,
            keyring=rotated_keyring,
        )
        == 'старое значение'
    )

    assert needs_rotation(
        encrypted,
        keyring=rotated_keyring,
    )


def test_current_key_does_not_need_rotation():
    """Значение на активном ключе не требует ротации."""
    keyring = make_keyring()

    encrypted = encrypt_text(
        'значение',
        keyring=keyring,
    )

    assert not needs_rotation(
        encrypted,
        keyring=keyring,
    )


def test_missing_old_key_fails():
    """Отсутствие нужного ключа не маскируется fallback-логикой."""
    old_keyring = make_keyring(
        primary='key-old',
    )
    encrypted = encrypt_text(
        'секрет',
        keyring=old_keyring,
    )

    new_keyring = make_keyring(
        primary='key-new',
    )

    with pytest.raises(EncryptionKeyNotFoundError):
        decrypt_text(
            encrypted,
            keyring=new_keyring,
        )


def test_corrupted_ciphertext_fails():
    """Повреждённый ciphertext не возвращается как обычный текст."""
    keyring = make_keyring()

    encrypted = encrypt_text(
        'секрет',
        keyring=keyring,
    )
    corrupted = f'{encrypted[:-4]}AAAA'

    with pytest.raises(InvalidEncryptedValueError):
        decrypt_text(
            corrupted,
            keyring=keyring,
        )


def test_unknown_format_fails():
    """Неизвестный формат значения считается ошибкой."""
    keyring = make_keyring()

    with pytest.raises(InvalidEncryptedValueError):
        decrypt_text(
            'plaintext',
            keyring=keyring,
        )


def test_primary_key_must_exist():
    """Активный ключ обязан присутствовать в keyring."""
    with pytest.raises(EncryptionConfigurationError):
        build_keyring(
            primary_key_id='missing',
            raw_keys={
                'other': generate_key(),
            },
        )


def test_key_id_cannot_contain_separator():
    """Идентификатор ключа не может конфликтовать с форматом ciphertext."""
    with pytest.raises(EncryptionConfigurationError):
        build_keyring(
            primary_key_id='bad:key',
            raw_keys={
                'bad:key': generate_key(),
            },
        )
