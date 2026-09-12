"""Шифрует чувствительные юридические и банковские данные."""

from datetime import date

import common.fields.encrypted
import users.validators.legal
from django.db import migrations, models

from common.encryption.providers import get_keyring
from users.migrations.utils.legal_encryption_v1 import (
    decrypt_value,
    encrypt_value,
)


IDENTITY_TEXT_FIELDS = (
    'registration_address',
    'passport_series',
    'passport_number',
    'passport_issued_by',
    'inn',
)

IDENTITY_DATE_FIELDS = (
    'birth_date',
    'passport_issue_date',
)

BANK_TEXT_FIELDS = (
    'bank_name',
    'bik',
    'correspondent_account',
    'checking_account',
)


def _temp_name(field_name):
    """Возвращает имя временного encrypted-поля."""
    return f'{field_name}_encrypted_tmp'


def _encrypt_checked(value, keyring, context):
    """Шифрует значение и сразу проверяет обратное преобразование."""
    if value == '':
        return ''

    encrypted = encrypt_value(value, keyring)

    if decrypt_value(encrypted, keyring) != value:
        raise RuntimeError(
            f'Не удалось проверить шифрование: {context}.',
        )

    return encrypted


def _encrypt_model(
    model,
    text_fields,
    date_fields,
    keyring,
    db_alias,
):
    """Переносит plaintext модели во временные encrypted-поля."""
    fields = (
        'pk',
        *text_fields,
        *date_fields,
    )

    queryset = (
        model.objects.using(db_alias)
        .only(*fields)
        .iterator(chunk_size=200)
    )

    for instance in queryset:
        updates = {}

        for field_name in text_fields:
            value = getattr(instance, field_name)

            if value is None:
                raise RuntimeError(
                    (
                        f'Неожиданный NULL в '
                        f'{model.__name__}.{field_name}, '
                        f'pk={instance.pk}.'
                    ),
                )

            context = (
                f'{model.__name__}.{field_name}, '
                f'pk={instance.pk}'
            )
            updates[_temp_name(field_name)] = _encrypt_checked(
                value,
                keyring,
                context,
            )

        for field_name in date_fields:
            value = getattr(instance, field_name)

            if value is None:
                updates[_temp_name(field_name)] = None
                continue

            plaintext = value.isoformat()
            context = (
                f'{model.__name__}.{field_name}, '
                f'pk={instance.pk}'
            )
            updates[_temp_name(field_name)] = _encrypt_checked(
                plaintext,
                keyring,
                context,
            )

        (
            model.objects.using(db_alias)
            .filter(pk=instance.pk)
            .update(**updates)
        )


def encrypt_legal_data(apps, schema_editor):
    """Шифрует существующие чувствительные данные."""
    keyring = get_keyring()
    db_alias = schema_editor.connection.alias

    identity_model = apps.get_model(
        'users',
        'ArtistIdentityData',
    )
    bank_model = apps.get_model(
        'users',
        'ArtistBankData',
    )

    _encrypt_model(
        identity_model,
        IDENTITY_TEXT_FIELDS,
        IDENTITY_DATE_FIELDS,
        keyring,
        db_alias,
    )
    _encrypt_model(
        bank_model,
        BANK_TEXT_FIELDS,
        (),
        keyring,
        db_alias,
    )


def _decrypt_model(
    model,
    text_fields,
    date_fields,
    keyring,
    db_alias,
):
    """Восстанавливает plaintext из временных encrypted-полей."""
    temp_fields = tuple(
        _temp_name(field_name)
        for field_name in (
            *text_fields,
            *date_fields,
        )
    )

    queryset = (
        model.objects.using(db_alias)
        .only('pk', *temp_fields)
        .iterator(chunk_size=200)
    )

    for instance in queryset:
        updates = {}

        for field_name in text_fields:
            encrypted = getattr(
                instance,
                _temp_name(field_name),
            )

            if encrypted is None:
                raise RuntimeError(
                    (
                        f'Неожиданный NULL в encrypted-поле '
                        f'{model.__name__}.{field_name}, '
                        f'pk={instance.pk}.'
                    ),
                )

            if encrypted == '':
                updates[field_name] = ''
                continue

            updates[field_name] = decrypt_value(
                encrypted,
                keyring,
            )

        for field_name in date_fields:
            encrypted = getattr(
                instance,
                _temp_name(field_name),
            )

            if encrypted is None:
                updates[field_name] = None
                continue

            plaintext = decrypt_value(
                encrypted,
                keyring,
            )

            try:
                updates[field_name] = date.fromisoformat(
                    plaintext,
                )
            except ValueError as exc:
                raise RuntimeError(
                    (
                        f'Некорректная дата после расшифровки '
                        f'{model.__name__}.{field_name}, '
                        f'pk={instance.pk}.'
                    ),
                ) from exc

        (
            model.objects.using(db_alias)
            .filter(pk=instance.pk)
            .update(**updates)
        )


def decrypt_legal_data(apps, schema_editor):
    """Восстанавливает plaintext при откате миграции."""
    keyring = get_keyring()
    db_alias = schema_editor.connection.alias

    identity_model = apps.get_model(
        'users',
        'ArtistIdentityData',
    )
    bank_model = apps.get_model(
        'users',
        'ArtistBankData',
    )

    _decrypt_model(
        identity_model,
        IDENTITY_TEXT_FIELDS,
        IDENTITY_DATE_FIELDS,
        keyring,
        db_alias,
    )
    _decrypt_model(
        bank_model,
        BANK_TEXT_FIELDS,
        (),
        keyring,
        db_alias,
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            'users',
            '0032_remove_artiststoresettings_returns_email_and_more',
        ),
    ]

    operations = [
        # Временно делаем старые строковые поля nullable.
        # Это необходимо для безопасного reverse RemoveField.
        migrations.AlterField(
            model_name='artistbankdata',
            name='bank_name',
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                verbose_name='Название банка',
            ),
        ),
        migrations.AlterField(
            model_name='artistbankdata',
            name='bik',
            field=models.CharField(
                blank=True,
                max_length=9,
                null=True,
                validators=[
                    users.validators.legal.validate_bik,
                ],
                verbose_name='БИК',
            ),
        ),
        migrations.AlterField(
            model_name='artistbankdata',
            name='checking_account',
            field=models.CharField(
                blank=True,
                max_length=20,
                null=True,
                validators=[
                    users.validators.legal.validate_checking_account,
                ],
                verbose_name='Расчетный счет',
            ),
        ),
        migrations.AlterField(
            model_name='artistbankdata',
            name='correspondent_account',
            field=models.CharField(
                blank=True,
                max_length=20,
                null=True,
                validators=[
                    users.validators.legal.validate_correspondent_account,
                ],
                verbose_name='Корреспондентский счет',
            ),
        ),
        migrations.AlterField(
            model_name='artistidentitydata',
            name='inn',
            field=models.CharField(
                blank=True,
                max_length=12,
                null=True,
                validators=[
                    users.validators.legal.validate_person_inn,
                ],
                verbose_name='ИНН',
            ),
        ),
        migrations.AlterField(
            model_name='artistidentitydata',
            name='passport_issued_by',
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                verbose_name='Кем выдан паспорт',
            ),
        ),
        migrations.AlterField(
            model_name='artistidentitydata',
            name='passport_number',
            field=models.CharField(
                blank=True,
                max_length=6,
                null=True,
                validators=[
                    users.validators.legal.validate_passport_number,
                ],
                verbose_name='Номер паспорта',
            ),
        ),
        migrations.AlterField(
            model_name='artistidentitydata',
            name='passport_series',
            field=models.CharField(
                blank=True,
                max_length=4,
                null=True,
                validators=[
                    users.validators.legal.validate_passport_series,
                ],
                verbose_name='Серия паспорта',
            ),
        ),
        migrations.AlterField(
            model_name='artistidentitydata',
            name='registration_address',
            field=models.CharField(
                blank=True,
                max_length=500,
                null=True,
                verbose_name='Адрес регистрации',
            ),
        ),

        # Временные TEXT-колонки под ciphertext.
        migrations.AddField(
            model_name='artistbankdata',
            name='bank_name_encrypted_tmp',
            field=models.TextField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='artistbankdata',
            name='bik_encrypted_tmp',
            field=models.TextField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='artistbankdata',
            name='checking_account_encrypted_tmp',
            field=models.TextField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='artistbankdata',
            name='correspondent_account_encrypted_tmp',
            field=models.TextField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='artistidentitydata',
            name='birth_date_encrypted_tmp',
            field=models.TextField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='artistidentitydata',
            name='inn_encrypted_tmp',
            field=models.TextField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='artistidentitydata',
            name='passport_issue_date_encrypted_tmp',
            field=models.TextField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='artistidentitydata',
            name='passport_issued_by_encrypted_tmp',
            field=models.TextField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='artistidentitydata',
            name='passport_number_encrypted_tmp',
            field=models.TextField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='artistidentitydata',
            name='passport_series_encrypted_tmp',
            field=models.TextField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='artistidentitydata',
            name='registration_address_encrypted_tmp',
            field=models.TextField(
                blank=True,
                null=True,
            ),
        ),

        # Пока plaintext ещё существует, создаём и проверяем ciphertext.
        migrations.RunPython(
            encrypt_legal_data,
            decrypt_legal_data,
        ),

        # После успешной проверки plaintext-колонки можно удалить.
        migrations.RemoveField(
            model_name='artistbankdata',
            name='bank_name',
        ),
        migrations.RemoveField(
            model_name='artistbankdata',
            name='bik',
        ),
        migrations.RemoveField(
            model_name='artistbankdata',
            name='checking_account',
        ),
        migrations.RemoveField(
            model_name='artistbankdata',
            name='correspondent_account',
        ),
        migrations.RemoveField(
            model_name='artistidentitydata',
            name='birth_date',
        ),
        migrations.RemoveField(
            model_name='artistidentitydata',
            name='inn',
        ),
        migrations.RemoveField(
            model_name='artistidentitydata',
            name='passport_issue_date',
        ),
        migrations.RemoveField(
            model_name='artistidentitydata',
            name='passport_issued_by',
        ),
        migrations.RemoveField(
            model_name='artistidentitydata',
            name='passport_number',
        ),
        migrations.RemoveField(
            model_name='artistidentitydata',
            name='passport_series',
        ),
        migrations.RemoveField(
            model_name='artistidentitydata',
            name='registration_address',
        ),

        # Возвращаем исходные имена колонок уже для ciphertext.
        migrations.RenameField(
            model_name='artistbankdata',
            old_name='bank_name_encrypted_tmp',
            new_name='bank_name',
        ),
        migrations.RenameField(
            model_name='artistbankdata',
            old_name='bik_encrypted_tmp',
            new_name='bik',
        ),
        migrations.RenameField(
            model_name='artistbankdata',
            old_name='checking_account_encrypted_tmp',
            new_name='checking_account',
        ),
        migrations.RenameField(
            model_name='artistbankdata',
            old_name='correspondent_account_encrypted_tmp',
            new_name='correspondent_account',
        ),
        migrations.RenameField(
            model_name='artistidentitydata',
            old_name='birth_date_encrypted_tmp',
            new_name='birth_date',
        ),
        migrations.RenameField(
            model_name='artistidentitydata',
            old_name='inn_encrypted_tmp',
            new_name='inn',
        ),
        migrations.RenameField(
            model_name='artistidentitydata',
            old_name='passport_issue_date_encrypted_tmp',
            new_name='passport_issue_date',
        ),
        migrations.RenameField(
            model_name='artistidentitydata',
            old_name='passport_issued_by_encrypted_tmp',
            new_name='passport_issued_by',
        ),
        migrations.RenameField(
            model_name='artistidentitydata',
            old_name='passport_number_encrypted_tmp',
            new_name='passport_number',
        ),
        migrations.RenameField(
            model_name='artistidentitydata',
            old_name='passport_series_encrypted_tmp',
            new_name='passport_series',
        ),
        migrations.RenameField(
            model_name='artistidentitydata',
            old_name='registration_address_encrypted_tmp',
            new_name='registration_address',
        ),

        # Финальный migration state совпадает с текущими моделями.
        migrations.AlterField(
            model_name='artistbankdata',
            name='bank_name',
            field=common.fields.encrypted.EncryptedCharField(
                blank=True,
                max_length=255,
                verbose_name='Название банка',
            ),
        ),
        migrations.AlterField(
            model_name='artistbankdata',
            name='bik',
            field=common.fields.encrypted.EncryptedCharField(
                blank=True,
                max_length=9,
                validators=[
                    users.validators.legal.validate_bik,
                ],
                verbose_name='БИК',
            ),
        ),
        migrations.AlterField(
            model_name='artistbankdata',
            name='checking_account',
            field=common.fields.encrypted.EncryptedCharField(
                blank=True,
                max_length=20,
                validators=[
                    users.validators.legal.validate_checking_account,
                ],
                verbose_name='Расчетный счет',
            ),
        ),
        migrations.AlterField(
            model_name='artistbankdata',
            name='correspondent_account',
            field=common.fields.encrypted.EncryptedCharField(
                blank=True,
                max_length=20,
                validators=[
                    users.validators.legal.validate_correspondent_account,
                ],
                verbose_name='Корреспондентский счет',
            ),
        ),
        migrations.AlterField(
            model_name='artistidentitydata',
            name='birth_date',
            field=common.fields.encrypted.EncryptedDateField(
                blank=True,
                null=True,
                validators=[
                    users.validators.legal.validate_birth_date,
                ],
                verbose_name='Дата рождения',
            ),
        ),
        migrations.AlterField(
            model_name='artistidentitydata',
            name='inn',
            field=common.fields.encrypted.EncryptedCharField(
                blank=True,
                max_length=12,
                validators=[
                    users.validators.legal.validate_person_inn,
                ],
                verbose_name='ИНН',
            ),
        ),
        migrations.AlterField(
            model_name='artistidentitydata',
            name='passport_issue_date',
            field=common.fields.encrypted.EncryptedDateField(
                blank=True,
                null=True,
                validators=[
                    users.validators.legal.validate_passport_issue_date,
                ],
                verbose_name='Дата выдачи паспорта',
            ),
        ),
        migrations.AlterField(
            model_name='artistidentitydata',
            name='passport_issued_by',
            field=common.fields.encrypted.EncryptedCharField(
                blank=True,
                max_length=255,
                verbose_name='Кем выдан паспорт',
            ),
        ),
        migrations.AlterField(
            model_name='artistidentitydata',
            name='passport_number',
            field=common.fields.encrypted.EncryptedCharField(
                blank=True,
                max_length=6,
                validators=[
                    users.validators.legal.validate_passport_number,
                ],
                verbose_name='Номер паспорта',
            ),
        ),
        migrations.AlterField(
            model_name='artistidentitydata',
            name='passport_series',
            field=common.fields.encrypted.EncryptedCharField(
                blank=True,
                max_length=4,
                validators=[
                    users.validators.legal.validate_passport_series,
                ],
                verbose_name='Серия паспорта',
            ),
        ),
        migrations.AlterField(
            model_name='artistidentitydata',
            name='registration_address',
            field=common.fields.encrypted.EncryptedCharField(
                blank=True,
                max_length=500,
                verbose_name='Адрес регистрации',
            ),
        ),
    ]
