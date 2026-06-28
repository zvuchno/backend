"""Модуль содержит описание модели Payment для интеграции с платежным шлюзом.

Модель обеспечивает связку заказов с транзакциями, хранение статусов
оплаты и данных для аудита финансовых операций.
"""

import uuid

from django.db import models

from store.constants import (
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import Order
from users.models.abstract import TimestampModel


class Payment(TimestampModel):
    """Платеж по заказу."""

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Ожидает оплаты'
        SUCCEEDED = 'succeeded', 'Оплачен'
        CANCELED = 'canceled', 'Отменён'
        FAILED = 'failed', 'Ошибка'

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Заказ',
    )
    provider_payment_id = models.CharField(
        'ID платежа в ЮKassa',
        max_length=MAX_CHAR_LENGTH,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )
    amount = models.DecimalField(
        'Сумма платежа',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
    )
    status = models.CharField(
        'Статус платежа',
        max_length=MAX_CHAR_LENGTH,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    paid_at = models.DateTimeField(
        'Дата и время оплаты',
        null=True,
        blank=True,
    )
    idempotency_key = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        verbose_name='Ключ идемпотентности',
    )
    error_code = models.CharField(
        'Код ошибки',
        max_length=MAX_CHAR_LENGTH,
        null=True,
        blank=True,
        help_text='Код ошибки, полученный от платежного провайдера',
    )

    class Meta:
        verbose_name = 'платеж'
        verbose_name_plural = 'платежи'

    def __str__(self):
        payment_id = self.provider_payment_id or 'без ID'
        return (
            f'Платеж {payment_id} ({self.get_status_display()}) '
            f'для заказа {self.order.order_number}',
        )
