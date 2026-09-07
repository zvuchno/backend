from django.conf import settings
from django.db import models

from common.models.abstract import TimestampModel


class EmailVerificationCode(TimestampModel):
    """Хранит активный код подтверждения email пользователя."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_verification_code',
        verbose_name='Пользователь',
    )
    code_hash = models.CharField(
        'Хэш кода',
        max_length=128,
    )
    expires_at = models.DateTimeField(
        'Действует до',
    )
    attempts = models.PositiveSmallIntegerField(
        'Количество попыток',
        default=0,
    )

    class Meta:
        verbose_name = 'код подтверждения email'
        verbose_name_plural = 'коды подтверждения email'

    def __str__(self):
        return f'Код подтверждения email: {self.user}'
