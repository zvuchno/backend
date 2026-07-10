"""Модуль описания моделей данных для логистики и отправлений через СДЭК."""

from django.db import models

from users.models.abstract import TimestampModel


class Shipment(TimestampModel):
    """Модель отправления (посылки) СДЭК.

    Используется для разделения единого заказа покупателя на несколько посылок,
    если в корзине присутствуют товары от разных артистов с
    разными точками отгрузки. Каждое отправление регистрируется в СДЭК
    независимо и имеет свой трек-номер.
    """

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
        max_length=100,
        blank=True,
        null=True,
        verbose_name='UUID транзакции СДЭК',
        help_text='Уникальный идентификатор запроса в API СДЭК '
        'для отслеживания статуса регистрации.',
    )
    state = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Состояние',
        help_text='Текущее состояние запроса',
    )
    tracking_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Номер накладной',
        help_text='Номер накладной СДЭК (cdek_number)',
    )
    weight = models.PositiveIntegerField(
        verbose_name='Вес (в граммах)',
        help_text='Общий физический вес посылки.',
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
