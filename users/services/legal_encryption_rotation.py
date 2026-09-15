"""Ротация шифрования юридических данных."""

from dataclasses import dataclass

from django.db import connections

from common.encryption.codec import (
    decrypt_text,
    encrypt_text,
    needs_rotation,
)
from common.encryption.providers import get_keyring

from users.models import ArtistBankData, ArtistIdentityData

IDENTITY_ENCRYPTED_FIELDS = (
    'birth_date',
    'registration_address',
    'passport_series',
    'passport_number',
    'passport_issued_by',
    'passport_issue_date',
    'inn',
)

BANK_ENCRYPTED_FIELDS = (
    'bank_name',
    'bik',
    'correspondent_account',
    'checking_account',
)


@dataclass
class EncryptionRotationResult:
    """Результат ротации encrypted-полей."""

    checked: int = 0
    outdated: int = 0
    rotated: int = 0
    concurrent_skips: int = 0


class LegalEncryptionRotationService:
    """Перешифровывает legal-данные актуальным ключом."""

    MODELS_AND_FIELDS = (
        (
            ArtistIdentityData,
            IDENTITY_ENCRYPTED_FIELDS,
        ),
        (
            ArtistBankData,
            BANK_ENCRYPTED_FIELDS,
        ),
    )

    @classmethod
    def rotate(
        cls,
        *,
        dry_run: bool = False,
        using: str = 'default',
    ) -> EncryptionRotationResult:
        """Перешифровывает значения устаревшими ключами."""
        keyring = get_keyring()
        connection = connections[using]
        result = EncryptionRotationResult()

        for model, field_names in cls.MODELS_AND_FIELDS:
            for field_name in field_names:
                cls._rotate_field(
                    connection=connection,
                    model=model,
                    field_name=field_name,
                    keyring=keyring,
                    result=result,
                    dry_run=dry_run,
                )

        return result

    @staticmethod
    def _rotate_field(
        *,
        connection,
        model,
        field_name: str,
        keyring,
        result: EncryptionRotationResult,
        dry_run: bool,
    ) -> None:
        """Перешифровывает одно поле модели."""
        table_name = connection.ops.quote_name(
            model._meta.db_table,
        )
        pk_column = connection.ops.quote_name(
            model._meta.pk.column,
        )
        field = model._meta.get_field(field_name)
        field_column = connection.ops.quote_name(
            field.column,
        )

        select_sql = (
            f'SELECT {pk_column}, {field_column} '
            f'FROM {table_name} '
            f'WHERE {field_column} IS NOT NULL '
            f"AND {field_column} <> ''"
        )

        with connection.cursor() as cursor:
            cursor.execute(select_sql)
            rows = cursor.fetchall()

        for pk, encrypted in rows:
            result.checked += 1

            plaintext = decrypt_text(
                encrypted,
                keyring=keyring,
            )

            if not needs_rotation(
                encrypted,
                keyring=keyring,
            ):
                continue

            result.outdated += 1

            if dry_run:
                continue

            rotated = encrypt_text(
                plaintext,
                keyring=keyring,
            )

            update_sql = (
                f'UPDATE {table_name} '
                f'SET {field_column} = %s '
                f'WHERE {pk_column} = %s '
                f'AND {field_column} = %s'
            )

            with connection.cursor() as cursor:
                cursor.execute(
                    update_sql,
                    (
                        rotated,
                        pk,
                        encrypted,
                    ),
                )

                if cursor.rowcount == 1:
                    result.rotated += 1
                else:
                    result.concurrent_skips += 1
