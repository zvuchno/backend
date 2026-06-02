"""Модуль расширения QuerySet для модели позиций корзин."""

from django.db import models
from django.db.models import (
    Case,
    DecimalField,
    ExpressionWrapper,
    F,
    Value,
    When,
)
from django.db.models.functions import Coalesce

from store.constants import (
    MAX_PRICE_DIGITS,
    MONEY_INTERNAL_PRECISION,
)


class CartItemQuerySet(models.QuerySet):
    """Кверисет для позиций корзины."""

    def with_prices(self):
        """Аннотирует каждый CartItem актуальной ценой и суммой строки.

        Рассчитывает цену за единицу (_unit_price) с учетом 'allow_overpay':
           - Если переплата разрешена, приоритет у 'price_with_donation',
             иначе — базовая цена продукта.
           - Если переплата запрещена — всегда базовая цена.
        Рассчитывает итог строки (_line_total) как (_unit_price * quantity).

        Используется:
        - В API и админке для отображения списка товаров без N+1 запросов.
        - В методе Cart.subtotal (fallback) для расчета суммы корзины.

        Внимание: Изменения в логике этого метода должны быть синхронизированы
        с CartQuerySet.with_subtotal, который дублирует расчет для оптимизации.

        Возвращает:
            QuerySet: кверисет с аннотированными полями '_unit_price'
            и '_line_total' (тип Decimal).
        """
        return (
            self
            .select_related(
                'product_variant__product',
            )
            .annotate(
                # _unit_price — цена за единицу с учётом allow_overpay
                _unit_price=Case(
                    When(
                        product_variant__product__allow_overpay=True,
                        then=Coalesce(
                            F('price_with_donation'),
                            F('product_variant__product__price'),
                        ),
                    ),
                    default=F('product_variant__product__price'),
                    output_field=DecimalField(
                        max_digits=MAX_PRICE_DIGITS,
                        decimal_places=MONEY_INTERNAL_PRECISION,
                    ),
                ),
            )
            .annotate(
                # _line_total — итог по строке (для агрегации и свойства)
                _line_total=ExpressionWrapper(
                    F('_unit_price') * F('quantity'),
                    output_field=DecimalField(
                        max_digits=MAX_PRICE_DIGITS,
                        decimal_places=MONEY_INTERNAL_PRECISION,
                    ),
                ),
            )
        )

    def with_item_cart_annotations(self):
        """Добавляет вычисляемые поля позиций корзины."""
        p = 'product_variant__product'

        carrier_album_condition = {
            f'{p}__product_type': 'merch',
            'is_carrier': True,
            f'{p}__merch__album_id__isnull': False,
        }

        return self.annotate(
            is_carrier=Coalesce(
                F(f'{p}__merch__kind__is_carrier'),
                Value(False),
            ),
            artist_name=Coalesce(
                F(f'{p}__album__owner__artist_profile__name'),
                F(f'{p}__track__owner__artist_profile__name'),
                F(f'{p}__merch__owner__artist_profile__name'),
            ),
            kind=Case(
                When(
                    **{
                        f'{p}__product_type': 'album',
                        f'{p}__album__is_single': True,
                    },
                    then=Value('Сингл'),
                ),
                When(
                    **{
                        f'{p}__product_type': 'album',
                        f'{p}__album__is_single': False,
                    },
                    then=Value('Альбом'),
                ),
                When(
                    **{f'{p}__product_type': 'track'},
                    then=Value('Трек'),
                ),
                When(
                    **{f'{p}__product_type': 'merch'},
                    then=F(f'{p}__merch__kind__name'),
                ),
                output_field=models.CharField(),
            ),
            target_type=Case(
                When(
                    **carrier_album_condition,
                    then=Value('album'),
                ),
                default=F(f'{p}__product_type'),
                output_field=models.CharField(),
            ),
            target_id=Case(
                When(
                    **carrier_album_condition,
                    then=F(f'{p}__merch__album_id'),
                ),
                When(
                    **{f'{p}__product_type': 'album'},
                    then=F(f'{p}__album_id'),
                ),
                When(
                    **{f'{p}__product_type': 'merch'},
                    then=F(f'{p}__merch_id'),
                ),
                When(
                    **{f'{p}__product_type': 'track'},
                    then=F(f'{p}__track_id'),
                ),
                output_field=models.IntegerField(),
            ),
        )
