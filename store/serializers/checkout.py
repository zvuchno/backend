"""Сериализатор данных оформления заказа."""

from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers

from .delivery import DeliverySerializer
from store.constants import (
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import Delivery, Product
from users.models import ArtistPickupPoint


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
    cdek_delivery_mode = serializers.ChoiceField(
        choices=[
            ('office', 'Самовывоз из ПВЗ'),
            ('door', 'Курьер (до двери)'),
            ('pickup', 'Постомат'),
        ],
        required=False,
        allow_blank=True,
    )
    delivery_point = serializers.CharField(
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

        if delivery.delivery_type == Delivery.DeliveryType.COURIER:
            self._validate_delivery_address(attrs)
        elif delivery.delivery_type == Delivery.DeliveryType.PICKPOINT:
            self._clear_street_address_fields(attrs)
            self._validate_pickpoint_fields(attrs)
        else:
            self._clear_address_fields(attrs)

        return attrs

    def _validate_pickpoint_fields(self, attrs) -> None:
        """Проверяет обязательные поля для доставки в ПВЗ."""
        self._validate_required_fields(
            attrs,
            {
                'cdek_delivery_mode': 'Метод доставки для СДЭК обязателен.',
                'city': 'Город обязателен для выбора пункта выдачи.',
                'delivery_point': 'Код пункта выдачи обязателен.',
            },
        )

    def _validate_delivery_address(self, attrs) -> None:
        """Проверяет обязательные поля адреса для доставки до двери."""
        self._validate_required_fields(
            attrs,
            {
                'cdek_delivery_mode': 'Метод доставки для СДЭК обязателен.',
                'city': 'Город обязателен для доставки.',
                'street': 'Улица обязательна для доставки.',
                'house': 'Номер дома обязателен.',
            },
        )

    @staticmethod
    def _validate_required_fields(attrs, required_fields) -> None:
        """Проверяет обязательные поля."""
        errors = {}

        for field, message in required_fields.items():
            if not attrs.get(field):
                errors[field] = message

        if errors:
            raise serializers.ValidationError(errors)

    @staticmethod
    def _clear_address_fields(attrs) -> None:
        """Очищает поля доставки, не используемые для выбранного типа."""
        attrs['city'] = ''
        attrs['street'] = ''
        attrs['house'] = ''
        attrs['apartment'] = ''
        attrs['delivery_point'] = ''

    @staticmethod
    def _clear_street_address_fields(attrs) -> None:
        """Очищает поля адреса, не используемые для ПВЗ."""
        attrs['street'] = ''
        attrs['house'] = ''
        attrs['apartment'] = ''


class UserDefaultsSerializer(serializers.Serializer):
    """Дефолтные данные пользователя для оформления заказа."""

    full_name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    city = serializers.CharField(allow_blank=True)


class ArtistPickupPointsSerializer(serializers.ModelSerializer):
    """Сериализатор для конкретной точки самовывоза мерча артиста."""

    date = serializers.DateField(source='pickup_date')

    class Meta:
        model = ArtistPickupPoint
        fields = ['id', 'address', 'date']


class CheckoutInfoSerializer(serializers.Serializer):
    """Данные для страницы оформления заказа."""

    user_defaults = UserDefaultsSerializer()
    subtotal = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
    )
    deliveries = DeliverySerializer(many=True)
    pickup_points = ArtistPickupPointsSerializer(many=True)
