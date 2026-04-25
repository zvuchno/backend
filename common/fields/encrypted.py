"""Обертки над зашифрованными полями модели."""

from django.conf import settings
from django.db import models

if settings.FIELD_ENCRYPTION_ENABLED:
    from encrypted_fields.fields import (
        EncryptedCharField,
        EncryptedDateField,
        EncryptedTextField,
    )
else:
    EncryptedCharField = models.CharField
    EncryptedDateField = models.DateField
    EncryptedTextField = models.TextField
