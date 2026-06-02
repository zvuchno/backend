"""Сериализатор для работы с промокодами артиста.

Поддерживает процентную и фиксированную скидку.
Поле owner подставляется автоматически из request.user во ViewSet.
"""

from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from store.constants import (
    DISCOUNT_VALUE_PRECISION,
    MAX_PRICE_DIGITS,
    MAX_PROMOCODE_LENGTH,
)
from store.models import Promocode
from store.validators import validate_promocode_format


class PromocodeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Promocode."""

    class Meta:
        model = Promocode
        fields = (
            'id',
            'code',
            'discount_value',
            'start_at',
            'end_at',
            'usage_limit',
            'used_count',
            'is_enabled',
        )
        read_only_fields = (
            'id',
            'used_count',
        )


class PromocodeReadDetailSerializer(PromocodeReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Promocode."""

    class Meta(PromocodeReadSerializer.Meta):
        fields = PromocodeReadSerializer.Meta.fields + (
            'description',
            'discount_type',
        )


class PromocodeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления Promocode."""

    code = serializers.CharField(
        max_length=MAX_PROMOCODE_LENGTH,
        required=True,
        validators=[
            validate_promocode_format,
            UniqueValidator(
                queryset=Promocode.objects.all(),
                message='Этот код уже занят.',
            ),
        ],
    )
    discount_type = serializers.ChoiceField(
        choices=Promocode.DiscountType.choices,
        required=True,
    )
    discount_value = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=DISCOUNT_VALUE_PRECISION,
        required=True,
    )

    class Meta:
        model = Promocode
        fields = (
            'code',
            'description',
            'usage_limit',
            'discount_type',
            'discount_value',
            'start_at',
            'end_at',
            'is_enabled',
        )

    def validate_code(self, value):
        if self.instance is not None and self.instance.code != value:
            raise serializers.ValidationError(
                'Код промокода нельзя изменить.',
            )
        return value

    def validate_start_at(self, value):
        if (
            self.instance is None
            and value is not None
            and value < timezone.now()
        ):
            raise serializers.ValidationError(
                'Дата начала не может быть в прошлом.',
            )
        return value

    def validate_end_at(self, value):
        if (
            self.instance is None
            and value is not None
            and value < timezone.now()
        ):
            raise serializers.ValidationError(
                'Дата окончания не может быть в прошлом.',
            )
        return value

    def validate(self, attrs):
        start_at = attrs.get(
            'start_at',
            getattr(self.instance, 'start_at', None),
        )
        end_at = attrs.get('end_at', getattr(self.instance, 'end_at', None))
        discount_type = attrs.get(
            'discount_type',
            getattr(self.instance, 'discount_type', None),
        )
        discount_value = attrs.get(
            'discount_value',
            getattr(self.instance, 'discount_value', None),
        )

        if (
            discount_type == Promocode.DiscountType.PERCENT
            and discount_value is not None
            and discount_value > Decimal('100')
        ):
            raise serializers.ValidationError({
                'discount_value': (
                    'Скидка в процентах не может быть больше 100.'
                ),
            })

        if start_at and end_at and start_at >= end_at:
            raise serializers.ValidationError({
                'end_at': ('Дата окончания должна быть позже даты начала.'),
            })

        return attrs
