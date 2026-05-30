"""Модуль описания торговых предложений (SKU) для интернет-магазина."""

import uuid

from django.db import models, transaction

from store.constants import (
    MAX_CHAR_LENGTH,
)
from store.models import Product
from users.models.abstract import ActivatableModel, TimestampModel


class ProductVariant(ActivatableModel, TimestampModel):
    """Конкретная единица товара (SKU), доступная для покупки.

    Представляет конкретную конфигурацию продукта с ценой,
    остатком на складе и типом носителя.
    На уровне БД гарантирует уникальность носителя
    в рамках одного продукта.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
        verbose_name='Вариант продукта',
    )
    sku = models.CharField(
        'SKU',
        max_length=MAX_CHAR_LENGTH,
        unique=True,
        blank=True,
    )
    stock = models.PositiveIntegerField(
        'Доступно',
        default=0,
        null=True,
        blank=True,
        help_text='Наличие на складе',
    )
    property_value = models.CharField(
        'Значение свойства',
        max_length=MAX_CHAR_LENGTH,
        blank=True,
        null=True,
    )

    def generate_sku(self):
        """Генерирует уникальный SKU на основе типа продукта и его ID.

        Пример: ALB-12-V1 (Альбом №12, Вариант 1).
        """
        if not self.product or not self.product.product_type:
            return f'TMP-{uuid.uuid4().hex[:6].upper()}'

        p_type = self.product.product_type[:3].upper()  # ALB, TRA, MER
        p_id = self.product.content_id

        new_sku = f'{p_type}-{p_id}-V{self.id}'
        # Проверка на уникальность (на случай коллизий или ручного ввода)
        if ProductVariant.objects.filter(sku=new_sku).exists():
            return f'{new_sku}-{uuid.uuid4().hex[:2].upper()}'
        return new_sku

    def save(self, *args, **kwargs):
        """Сохраняет вариант и вызывет generate_sku после получения ID."""
        is_new = self._state.adding
        with transaction.atomic():
            super().save(*args, **kwargs)
            if is_new and not self.sku:
                self.sku = self.generate_sku()
                super().save(update_fields=['sku'])

    class Meta:
        verbose_name = 'вариант продукта'
        verbose_name_plural = 'варианты продукта'
        ordering = ('id',)
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'property_value'],
                name='unique_variant_value_per_product',
            ),
        ]

    @property
    def variant_name(self):
        """Генерирует имя варианта продукта: имя контента (свойство)."""
        if not self.product:
            return ''
        product_name = self.product.name
        if self.property_value:
            return f'{product_name} ({self.property_value})'
        return product_name

    def __str__(self):
        return f'{self.variant_name}'
