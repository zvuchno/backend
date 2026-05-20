"""Модели корзины покупок."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce

from store.constants import MAX_CHAR_LENGTH
from store.querysets import CartQuerySet
from users.models.abstract import TimestampModel


class Cart(TimestampModel):
    """Корзина пользователя."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart',
        verbose_name='Покупатель',
    )
    session_key = models.CharField(
        'Ключ сессии',
        max_length=MAX_CHAR_LENGTH,
        null=True,
        blank=True,
    )
    objects = CartQuerySet.as_manager()

    @property
    def subtotal(self):
        """Всегда возвращает правильную сумму."""
        # Проверяем, нет ли уже готового значения из БД
        if hasattr(self, '_subtotal'):
            return self._subtotal
        # Если нет, делаем агрегацию Fallback — одним запросом
        return self.items.with_prices().aggregate(
            total=Coalesce(Sum('_line_total'), Decimal('0.0000')),
        )['total']

    @property
    def discount_promocode(self):
        """Сумма скидки по промокоду."""
        return Decimal('0.0000')  # TODO: Пока не реализованы промокоды

    @property
    def total(self):
        """Сумма корзины с учетом промокода."""
        return self.subtotal  # TODO: Пока не реализованы промокоды, доделать

    def clean(self):
        super().clean()
        if not self.user and not self.session_key:
            raise ValidationError(
                'Корзина должна иметь владельца (пользователя или сессию).',
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'корзина'
        verbose_name_plural = 'корзины'
        constraints = [
            models.UniqueConstraint(
                fields=['session_key'],
                name='unique_session_cart',
                condition=models.Q(session_key__isnull=False),
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False)
                    | models.Q(session_key__isnull=False)
                ),
                name='cart_has_owner',
            ),
        ]

    def __str__(self):
        if self.user:
            return f'Корзина {self.user}'
        return f'Анонимная корзина [id: ...{str(self.session_key)[:16]}]'
