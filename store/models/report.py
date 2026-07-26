"""Модель для формирования отчетов."""

from django.db import models

from store.constants import (
    MAX_PRICE_DIGITS,
    MONEY_INTERNAL_PRECISION,
    ZERO_MONEY,
)
from users.models import ArtistProfile
from users.models.abstract import TimestampModel


def report_upload_path(instance, filename):
    """Путь для хранения файла отчета."""
    return (
        f'reports/artist_id_{instance.artist_id}/'
        f'{instance.period_type}/{filename}'
    )


class Report(TimestampModel):
    """Агрегированный отчет о продажах артиста за период."""

    class PeriodType(models.TextChoices):
        DAILY = 'day', 'День'
        MONTHLY = 'month', 'Месяц'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Формируется'
        READY = 'ready', 'Готов'
        FAILED = 'failed', 'Ошибка'

    artist = models.ForeignKey(
        ArtistProfile,
        on_delete=models.PROTECT,
        related_name='reports',
        verbose_name='Артист',
    )
    period_type = models.CharField(
        'Тип периода',
        max_length=10,
        choices=PeriodType.choices,
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
    orders_count = models.PositiveIntegerField(
        'Количество заказов',
        default=0,
    )
    items_count = models.PositiveIntegerField(
        'Количество проданных товаров',
        default=0,
    )
    gross_amount = models.DecimalField(
        'Валовая выручка, руб.',
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
    delivery_amount = models.DecimalField(
        'Стоимость доставки, руб.',
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
        ordering = ('-period_end', '-created_at')
        verbose_name = 'отчет'
        verbose_name_plural = 'отчеты'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'artist',
                    'period_type',
                    'period_start',
                    'period_end',
                ],
                name='unique_artist_report',
            ),
        ]

    def __str__(self):
        return (
            f'{self.artist_id} / '
            f'{self.period_type} / '
            f'{self.period_start}—{self.period_end}'
        )
