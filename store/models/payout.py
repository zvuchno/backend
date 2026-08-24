from django.conf import settings
from django.db import models

from common.models.abstract import TimestampModel

from store.constants import (
    MAX_PRICE_DIGITS,
    MONEY_INTERNAL_PRECISION,
    ZERO_MONEY,
)
from store.models.report import Report


class Payout(TimestampModel):
    """Выплата по агентскому отчету."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает выплаты'
        ON_HOLD = 'on_hold', 'Отложена'
        PAID = 'paid', 'Выплачено'

    report = models.OneToOneField(
        Report,
        on_delete=models.PROTECT,
        related_name='payout',
        verbose_name='Отчет',
    )
    payout_recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payouts',
        verbose_name='Получатель выплаты',
    )
    amount = models.DecimalField(
        'Сумма выплаты',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_INTERNAL_PRECISION,
        default=ZERO_MONEY,
    )
    status = models.CharField(
        'Статус выплаты',
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    comment = models.TextField(
        'Комментарий',
        blank=True,
    )
    paid_at = models.DateTimeField(
        'Дата выплаты',
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'выплата'
        verbose_name_plural = 'выплаты'

    def __str__(self):
        return (
            f'{self.payout_recipient.email} / '
            f'{self.report.period_start:%d.%m.%y} — '
            f'{self.report.period_end:%d.%m.%y}'
        )
