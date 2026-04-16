"""Модели заказов покупателя."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField

from store.constants import (
    MAX_CHAR_LENGTH,
    MAX_NUMBER_ORDER_LENGTH,
    MAX_PRICE_DIGITS,
    PRICE_DECIMAL_PLACES,
)
from users.models.abstract import TimestampModel


class OrderNumberCounter(models.Model):
    """Счётчик номеров заказов для конкретного года."""

    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)


class Order(TimestampModel):
    """Заказ, сформированный из корзины."""

    class Status(models.TextChoices):
        CREATED = 'created', 'Создан'
        CONFIRMED = 'confirmed', 'Ожидает оплаты'
        PAID = 'paid', 'Оплачен'
        SHIPPED = 'shipped', 'Отправлен'
        COMPLETED = 'completed', 'Завершен'
        CANCELED = 'canceled', 'Отменен'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name='Покупатель',
    )
    order_number = models.CharField(
        'Номер заказа',
        max_length=MAX_NUMBER_ORDER_LENGTH,
        unique=True,
        editable=False,
    )
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED,
    )

    # --- Контакты ---
    full_name = models.CharField(
        'Имя и фамилия',
        max_length=MAX_CHAR_LENGTH,
        default='',
    )
    email = models.EmailField('Email')
    phone = PhoneNumberField(
        'Номер телефона',
        help_text='Номер телефона',
    )

    # --- Адрес доставки ---
    city = models.CharField('Город', max_length=MAX_CHAR_LENGTH, blank=True)
    street = models.CharField('Улица', max_length=MAX_CHAR_LENGTH, blank=True)
    house = models.CharField('Дом', max_length=MAX_CHAR_LENGTH, blank=True)
    apartment = models.CharField(
        'Квартира/Офис',
        max_length=MAX_CHAR_LENGTH,
        blank=True,
    )

    delivery = models.ForeignKey(
        'store.Delivery',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name='Способ доставки',
    )
    items_total = models.DecimalField(
        'Сумма товаров (руб.)',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        default=Decimal('0.00'),
    )
    delivery_price = models.DecimalField(
        'Стоимость доставки (руб.)',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    grand_total = models.DecimalField(
        'Итого (руб.)',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        default=Decimal('0.00'),
    )
    comment = models.TextField(
        'Комментарий',
        help_text='Комментарий к заказу',
        null=True,
        blank=True,
    )

    def _generate_order_number(self) -> str:
        """Генерирует уникальный номер заказа с раздельной нумерацией по годам.

        Формат номера: ZV-YYXXXXXX.
        Для каждого года ведётся отдельный счётчик в базе данных.
        Инкремент выполняется атомарно (select_for_update), что
        гарантирует уникальность номеров при конкурентных запросах.
        """
        now = timezone.now()
        year = now.year
        short_year = str(year)[-2:]

        with transaction.atomic():
            counter, _ = (
                OrderNumberCounter.objects.select_for_update().get_or_create(
                    year=year,
                )
            )
            OrderNumberCounter.objects.filter(
                pk=counter.pk,
            ).update(last_number=F('last_number') + 1)
            counter.refresh_from_db()
        return f'ZV-{short_year}{counter.last_number:06d}'

    def save(self, *args, **kwargs):
        if not self.order_number:
            with transaction.atomic():
                self.order_number = self._generate_order_number()
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        default_related_name = 'orders'
        ordering = ('-created_at',)

    def __str__(self):
        return f'Заказ # {self.order_number} ({self.user})'
