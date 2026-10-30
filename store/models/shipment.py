"""Модуль описания моделей данных для логистики и отправлений через СДЭК."""

from django.core.validators import MinValueValidator
from django.db import models

from common.models.abstract import TimestampModel

from store.constants import (
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    MONEY_INTERNAL_PRECISION,
    ZERO_MONEY,
)


class Shipment(TimestampModel):
    """Модель отправления (посылки) СДЭК.

    Используется для разделения единого заказа покупателя на несколько посылок,
    если в корзине присутствуют товары от разных артистов с
    разными точками отгрузки. Каждое отправление регистрируется в СДЭК
    независимо и имеет свой трек-номер.
    """

    class State(models.TextChoices):
        """Состояния запроса на регистрацию отправления в API СДЭК."""

        CREATED = 'CREATED', 'Создан'
        ACCEPTED = 'ACCEPTED', 'Запрос принят'
        WAITING = 'WAITING', 'Ожидает обработки'
        SUCCESSFUL = 'SUCCESSFUL', 'Обработан'
        INVALID = 'INVALID', 'Ошибка'

    class DeliveryStatus(models.TextChoices):
        """Логистические статусы СДЭК.

        (обновление через вебхуки ORDER_STATUS).
        """

        CREATED = 'CREATED', 'Создан'
        REMOVED = 'REMOVED', 'Удален'
        RECEIVED_AT_SHIPMENT_WAREHOUSE = (
            'RECEIVED_AT_SHIPMENT_WAREHOUSE',
            'Принят на складе отправления',
        )
        READY_FOR_SHIPMENT_IN_SENDER_CITY = (
            'READY_FOR_SHIPMENT_IN_SENDER_CITY',
            'Готов к отправке в городе-отправителе',
        )
        TAKEN_BY_TRANSPORTER_FROM_SENDER_CITY = (
            'TAKEN_BY_TRANSPORTER_FROM_SENDER_CITY',
            'Сдан перевозчику в городе-отправителе',
        )
        SENT_TO_RECIPIENT_CITY = (
            'SENT_TO_RECIPIENT_CITY',
            'Отправлен в город-получатель',
        )
        ACCEPTED_IN_RECIPIENT_CITY = (
            'ACCEPTED_IN_RECIPIENT_CITY',
            'Встречен в городе-получателе',
        )
        ACCEPTED_AT_RECIPIENT_CITY_WAREHOUSE = (
            'ACCEPTED_AT_RECIPIENT_CITY_WAREHOUSE',
            'Принят на склад доставки',
        )
        ACCEPTED_AT_PICK_UP_POINT = (
            'ACCEPTED_AT_PICK_UP_POINT',
            'Принят в пункте выдачи (ПВЗ)',
        )
        ACCEPTED_AT_TRANSIT_WAREHOUSE = (
            'ACCEPTED_AT_TRANSIT_WAREHOUSE',
            'Принят в транзитном городе',
        )
        RETURNED_TO_SENDER_CITY_WAREHOUSE = (
            'RETURNED_TO_SENDER_CITY_WAREHOUSE',
            'Возвращен на склад отправителя',
        )
        RETURNED_TO_TRANSIT_WAREHOUSE = (
            'RETURNED_TO_TRANSIT_WAREHOUSE',
            'Возвращен на склад транзита',
        )
        RETURNED_TO_RECIPIENT_CITY_WAREHOUSE = (
            'RETURNED_TO_RECIPIENT_CITY_WAREHOUSE',
            'Возвращен на склад доставки',
        )
        READY_FOR_SHIPMENT_IN_TRANSIT_CITY = (
            'READY_FOR_SHIPMENT_IN_TRANSIT_CITY',
            'Выдан на отправку в городе-транзите',
        )
        TAKEN_BY_TRANSPORTER_FROM_TRANSIT_CITY = (
            'TAKEN_BY_TRANSPORTER_FROM_TRANSIT_CITY',
            'Сдан перевозчику в городе-транзите',
        )
        SENT_TO_SENDER_CITY = (
            'SENT_TO_SENDER_CITY',
            'Отправлен в город-отправитель',
        )
        ENTERED_TO_RECIPIENT_CITY_WAREHOUSE = (
            'ENTERED_TO_RECIPIENT_CITY_WAREHOUSE',
            'Поступил на склад доставки',
        )
        ENTERED_TO_PICK_UP_POINT = (
            'ENTERED_TO_PICK_UP_POINT',
            'Поступил в пункт выдачи (ПВЗ)',
        )
        POSTOMAT_POSTED = (
            'POSTOMAT_POSTED',
            'Заложен в постамат',
        )
        POSTOMAT_SEIZED = (
            'POSTOMAT_SEIZED',
            'Изъят из постамата курьером',
        )
        POSTOMAT_RECEIVED = (
            'POSTOMAT_RECEIVED',
            'Изъят из постамата клиентом',
        )
        TAKEN_BY_COURIER = 'TAKEN_BY_COURIER', 'Выдан на доставку'
        DELIVERED = 'DELIVERED', 'Вручен'
        NOT_DELIVERED = 'NOT_DELIVERED', 'Не вручен'
        INVALID = 'INVALID', 'Некорректный заказ'

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
        'Состояние запроса',
        max_length=20,
        choices=State.choices,
        blank=True,
        default=State.CREATED,
        help_text='Текущее состояние запроса',
    )
    delivery_status = models.CharField(
        'Статус доставки',
        max_length=50,
        choices=DeliveryStatus.choices,
        blank=True,
        default='',
        help_text='Логистический статус перемещения посылки в СДЭК',
    )
    delivery_status_changed_at = models.DateTimeField(
        'Время последнего статуса доставки',
        null=True,
        blank=True,
        help_text=(
            'Время события СДЭК, из которого взят текущий delivery_status. '
        ),
    )
    cdek_number = models.CharField(
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
            models.UniqueConstraint(
                fields=['cdek_uuid'],
                condition=~models.Q(cdek_uuid=''),
                name='unique_shipment_cdek_uuid',
            ),
        ]

    def __str__(self):
        return (
            f'Отправление от {self.artist} по заказу {self.order.order_number}'
        )


class ShipmentStatusEvent(TimestampModel):
    """История статусов отправления, полученных от СДЭК.

    Нужна для идемпотентности (повторный вебхук/опрос не создаёт дублей),
    разбора спорных ситуаций и показа истории в личном кабинете.
    """

    shipment = models.ForeignKey(
        'store.Shipment',
        on_delete=models.CASCADE,
        related_name='status_events',
        verbose_name='Отправление',
    )
    code = models.CharField(
        'Код статуса',
        max_length=50,
    )
    occurred_at = models.DateTimeField(
        'Время события в СДЭК',
    )
    raw = models.JSONField(
        'Исходные данные',
        default=dict,
        blank=True,
    )

    class Meta:
        verbose_name = 'событие статуса отправления'
        verbose_name_plural = 'события статусов отправлений'
        ordering = ['-occurred_at', '-pk']
        constraints = [
            models.UniqueConstraint(
                fields=['shipment', 'code', 'occurred_at'],
                name='unique_shipment_status_event',
            ),
        ]

    def __str__(self):
        return f'{self.shipment_id}: {self.code} ({self.occurred_at})'
