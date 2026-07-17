"""Модуль описания моделей данных для логистики и отправлений через СДЭК."""

from django.core.validators import MinValueValidator
from django.db import models

from store.constants import (
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    MONEY_INTERNAL_PRECISION,
    ZERO_MONEY,
)
from users.models.abstract import TimestampModel


class Shipment(TimestampModel):
    """Модель отправления (посылки) СДЭК.

    Используется для разделения единого заказа покупателя на несколько посылок,
    если в корзине присутствуют товары от разных артистов с
    разными точками отгрузки. Каждое отправление регистрируется в СДЭК
    независимо и имеет свой трек-номер.
    """

    class State(models.TextChoices):
        PENDING = 'PENDING', 'В ожидании'
        ACCEPTED = 'ACCEPTED', 'Принято'
        WAITING = 'WAITING', 'Ожидание'
        SUCCESSFUL = 'SUCCESSFUL', 'Успешно'
        INVALID = 'INVALID', 'Ошибка'

    order = models.ForeignKey(
        'store.Order',
        on_delete=models.CASCADE,
        related_name='shipments',
        verbose_name='Заказ',
        help_text='Заказ, к которому относится данное отправление.',
    )
    artist = models.ForeignKey(
        'users.ArtistProfile',
        on_delete=models.PROTECT,
        related_name='shipments',
        verbose_name='Артист',
        help_text='Артист, со склада которого уходит посылка.',
    )
    cdek_uuid = models.CharField(
        'UUID транзакции СДЭК',
        max_length=MAX_CHAR_LENGTH,
        blank=True,
        default='',
        help_text='Уникальный идентификатор запроса в API СДЭК '
        'для отслеживания статуса регистрации.',
    )
    state = models.CharField(
        'Состояние',
        max_length=20,
        choices=State.choices,
        blank=True,
        default='',
        help_text='Текущее состояние запроса',
    )
    tracking_number = models.CharField(
        'Номер накладной',
        max_length=MAX_CHAR_LENGTH,
        blank=True,
        default='',
        help_text='Номер накладной СДЭК (cdek_number)',
    )
    weight = models.PositiveIntegerField(
        'Вес (в граммах)',
        blank=True,
        null=True,
        help_text='Общий физический вес посылки.',
    )
    estimated_delivery_cost = models.DecimalField(
        'Расчетная стоимость доставки артиста (руб.)',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_INTERNAL_PRECISION,
        default=ZERO_MONEY,
        validators=[MinValueValidator(ZERO_MONEY)],
        help_text=(
            'Предварительная стоимость доставки, рассчитанная через API СДЭК. '
            'Может отличаться от фактической стоимости услуг.'
        ),
    )

    class Meta:
        verbose_name = 'отправление'
        verbose_name_plural = 'отправления'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'artist'],
                name='unique_order_artist_shipment',
            ),
        ]

    def __str__(self):
        return (
            f'Отправление от {self.artist} по заказу {self.order.order_number}'
        )
