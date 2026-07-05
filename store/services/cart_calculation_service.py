"""Сервисный слой для расчёта стоимостных показателей корзины покупок.

Модуль содержит бизнес-логику для калькуляции стоимости позиций, общего
субтотала, расчёта процентных и фиксированных скидок по промокодам с защитой
от ошибок округления (потери копеек) и оптимизацией базы данных (N+1).
"""

from decimal import Decimal

from store.constants import ZERO_MONEY
from store.models import Product, Promocode

ZERO_DISCOUNT = Decimal('0.00')
DISCOUNT_PRECISION = Decimal('0.01')


class CartCalculationService:
    """Сервис расчёта корзины.

    Отвечает за расчёт стоимостных показателей:
    - subtotal (сумма до скидок)
    - скидки по каждой конкретной позиции
    - общая сумма скидки по промокоду
    - итоговая сумма корзины (total) к оплате
    """

    def __init__(self, cart):
        """Инициализирует сервис и кэширует позиции корзины в память."""
        self.cart = cart

        self.items = list(
            cart.items.with_prices().select_related(
                'product_variant__product__album',
                'product_variant__product__track',
                'product_variant__product__merch',
            ),
        )

        self.promocode = cart.promocode

        self._discounts = None
        self._subtotal = None
        self._discount_total = None
        self._total = None

    def get_merch_artist_ids(self) -> list[int]:
        """Возвращает список ID уникальных артистов, чей мерч в корзине."""
        if not self.cart:
            return []

        return list(
            self.cart.items
            .filter(
                product_variant__product__product_type=Product.ProductType.MERCH,
                product_variant__product__merch__owner__artist_profile__isnull=False,
            )
            .values_list(
                'product_variant__product__merch__owner__artist_profile__id',
                flat=True,
            )
            .distinct(),
        )

    def get_subtotal(self) -> Decimal:
        """Возвращает общую сумму корзины до применения скидок."""
        if self._subtotal is not None:
            return self._subtotal

        self._subtotal = sum(
            (item.base_line_total for item in self.items),
            ZERO_MONEY,
        ).quantize(ZERO_MONEY)

        return self._subtotal

    def _get_item_owner_id(self, item) -> int | None:
        """Определяет ID владельца (артиста) для конкретной позиции в корзине.

        Необходимо для проверки применимости промокода, так как промокоды
        выпущены конкретными артистами для своих товаров.
        """
        return item.product_variant.product.content.owner_id

    def get_item_discounts(self) -> dict[int, Decimal]:
        """Рассчитывает и возвращает скидку для каждой позиции корзины.

        Возвращает:
            dict: {item_id: Decimal}
        """
        if self._discounts is not None:
            return self._discounts

        discounts = {item.id: ZERO_DISCOUNT for item in self.items}

        if not self.promocode or not self.promocode.is_available:
            self._discounts = discounts
            return discounts

        # Отбираем товары, автор которых совпадает с автором промокода
        applicable_items = [
            item
            for item in self.items
            if (
                self._get_item_owner_id(item) == self.promocode.owner_id
                and item.base_line_total > ZERO_DISCOUNT
            )
        ]

        if not applicable_items:
            self._discounts = discounts
            return discounts

        if self.promocode.discount_type == Promocode.DiscountType.PERCENT:
            self._calculate_percent_discount(discounts, applicable_items)

        elif self.promocode.discount_type == Promocode.DiscountType.FIXED:
            self._calculate_fixed_discount(discounts, applicable_items)

        self._discounts = discounts
        return discounts

    def _calculate_percent_discount(self, discounts, applicable_items) -> None:
        """Метод для расчёта процентной скидки."""
        discount_factor = self.promocode.discount_value / Decimal('100')

        for item in applicable_items:
            calculated_discount = item.base_line_total * discount_factor
            # Ограничиваем скидку стоимостью самого товара
            discounts[item.id] = min(
                calculated_discount,
                item.base_line_total,
            ).quantize(DISCOUNT_PRECISION)

    def _calculate_fixed_discount(self, discounts, applicable_items) -> None:
        """Метод для распределения фиксированной скидки."""
        total_applicable = sum(
            item.base_line_total for item in applicable_items
        )

        # Если общая сумма подходящих товаров равна 0 → нечего распределять
        if total_applicable <= ZERO_DISCOUNT:
            return

        discount_to_distribute = min(
            self.promocode.discount_value,
            total_applicable,
        )
        remaining = discount_to_distribute

        for index, item in enumerate(applicable_items):
            if index == len(applicable_items) - 1:
                # Чтобы избежать 'потери копеек' из-за округлений
                # при делении, последний товар забирает
                # весь остаток распределяемой суммы
                discounts[item.id] = remaining.quantize(DISCOUNT_PRECISION)
            else:
                # Расчитываем долю конкретной позиции в общем обороте
                # применимых товаров: Share = Item_Total / Total_Applicable
                # Скидка на позицию = Общая_Скидка * Share
                share = item.base_line_total / total_applicable
                item_discount = (discount_to_distribute * share).quantize(
                    DISCOUNT_PRECISION,
                )

                discounts[item.id] = item_discount
                remaining -= item_discount

    def get_discount_total(self) -> Decimal:
        """Общая сумма скидки по применённому промокоду."""
        if self._discount_total is not None:
            return self._discount_total

        self._discount_total = sum(
            self.get_item_discounts().values(),
            ZERO_MONEY,
        ).quantize(ZERO_MONEY)

        return self._discount_total

    def get_total(self) -> Decimal:
        """Финальная стоимость корзины после вычета скидок."""
        if self._total is not None:
            return self._total

        self._total = (
            self.get_subtotal() - self.get_discount_total()
        ).quantize(ZERO_MONEY)

        return self._total

    def get_item_line_total(self, item) -> Decimal:
        """Чистая стоимость конкретной позиции после применения скидки."""
        discount = self.get_item_discounts().get(item.id, ZERO_DISCOUNT)

        return (item.base_line_total - discount).quantize(ZERO_MONEY)

    def get_serializer_context(self) -> dict:
        """Контекст для сериализаторов."""
        return {
            'cart_service': self,
            'subtotal': self.get_subtotal(),
            'discount_promocode': self.get_discount_total(),
            'total': self.get_total(),
        }
