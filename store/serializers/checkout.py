"""Сериализатор данных оформления заказа."""

from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers

from store.constants import MAX_CHAR_LENGTH
from store.models import Delivery, Product


class CheckoutSerializer(serializers.Serializer):
    """Сериализатор оформления заказа.

    Валидирует:
    - контактные данные покупателя
    - согласие на обработку персональных данных
    - способ доставки
    - обязательность адреса для физических товаров
    """

    full_name = serializers.CharField(
        max_length=MAX_CHAR_LENGTH,
    )
    email = serializers.EmailField()
    phone = PhoneNumberField()

    personal_data_consent = serializers.BooleanField(
        write_only=True,
    )

    city = serializers.CharField(
        max_length=MAX_CHAR_LENGTH,
        required=False,
        allow_blank=True,
    )
    street = serializers.CharField(
        max_length=MAX_CHAR_LENGTH,
        required=False,
        allow_blank=True,
    )
    house = serializers.CharField(
        max_length=MAX_CHAR_LENGTH,
        required=False,
        allow_blank=True,
    )
    apartment = serializers.CharField(
        max_length=MAX_CHAR_LENGTH,
        required=False,
        allow_blank=True,
    )

    delivery = serializers.PrimaryKeyRelatedField(
        queryset=Delivery.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    def validate_personal_data_consent(self, value):
        """Проверяет согласие на обработку персональных данных."""
        if not value:
            raise serializers.ValidationError(
                'Необходимо согласие на обработку персональных данных.',
            )

        return value

    def validate_email(self, value):
        """Нормализует email."""
        return value.strip().lower()

    def validate(self, attrs):
        """Проверяет данные оформления заказа."""
        cart = self.context['cart']

        cart_items = cart.items.select_related(
            'product_variant__product',
        )

        if not cart_items.exists():
            raise serializers.ValidationError({
                'cart': 'Корзина пуста.',
            })

        has_merch = cart_items.filter(
            product_variant__product__product_type=Product.ProductType.MERCH,
        ).exists()

        if not has_merch:
            attrs['delivery'] = None
            self._clear_address_fields(attrs)
            return attrs

        delivery = attrs.get('delivery')

        if not delivery:
            raise serializers.ValidationError({
                'delivery': (
                    'Выберите способ доставки для физических товаров.'
                ),
            })

        if delivery.delivery_type != Delivery.DeliveryType.PICKUP:
            self._validate_delivery_address(attrs)
        else:
            self._clear_address_fields(attrs)

        return attrs

    def _validate_delivery_address(self, attrs) -> None:
        """Проверяет обязательные поля адреса доставки."""
        errors = {}

        required_fields = {
            'city': 'Город обязателен для доставки.',
            'street': 'Улица обязательна для доставки.',
            'house': 'Номер дома обязателен.',
        }

        for field, message in required_fields.items():
            if not attrs.get(field):
                errors[field] = message

        if errors:
            raise serializers.ValidationError(errors)

    @staticmethod
    def _clear_address_fields(attrs) -> None:
        """Очищает адресные поля."""
        attrs['city'] = ''
        attrs['street'] = ''
        attrs['house'] = ''
        attrs['apartment'] = ''
