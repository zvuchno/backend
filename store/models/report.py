"""Модель для формирования отчетов."""

from django.conf import settings
from django.db import models

from common.models.abstract import TimestampModel

from store.constants import (
    MAX_PRICE_DIGITS,
    MONEY_INTERNAL_PRECISION,
    ZERO_MONEY,
)


def report_upload_path(instance, filename):
    """Путь для хранения файла отчета."""
    return (
        f'reports/recipient_id_{instance.payout_recipient_id}/'
        f'{instance.period_start:%Y-%m}/{filename}'
    )


class Report(TimestampModel):
    """Агрегированный отчет о продажах за месяц."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Формируется'
        READY = 'ready', 'Готов'
        FAILED = 'failed', 'Ошибка'

    payout_recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reports',
        verbose_name='Получатель выплаты',
    )
    status = models.CharField(
        'Статус отчета',
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    period_start = models.DateField(
        'Начало периода',
    )
    period_end = models.DateField(
        'Конец периода',
    )
    sales_amount = models.DecimalField(
        'Сумма проданных товаров, руб.',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_INTERNAL_PRECISION,
        default=ZERO_MONEY,
    )
    donation_amount = models.DecimalField(
        'Сумма доплат, руб.',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_INTERNAL_PRECISION,
        default=ZERO_MONEY,
    )
    discount_amount = models.DecimalField(
        'Сумма скидок, руб.',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_INTERNAL_PRECISION,
        default=ZERO_MONEY,
    )
    commission_amount = models.DecimalField(
        'Комиссия платформы, руб.',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_INTERNAL_PRECISION,
        default=ZERO_MONEY,
    )
    payout_amount = models.DecimalField(
        'Сумма к выплате, руб.',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_INTERNAL_PRECISION,
        default=ZERO_MONEY,
    )

    report_file = models.FileField(
        'Файл отчета',
        upload_to=report_upload_path,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'отчет'
        verbose_name_plural = 'отчеты'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'payout_recipient',
                    'period_start',
                    'period_end',
                ],
                name='unique_payout_recipient_report',
            ),
        ]

    def __str__(self):
        return (
            f'{self.payout_recipient.email} (ID: '
            f'{self.payout_recipient_id}) / '
            f'{self.period_start.strftime("%d.%m.%y")} — '
            f'{self.period_end.strftime("%d.%m.%y")}'
        )
