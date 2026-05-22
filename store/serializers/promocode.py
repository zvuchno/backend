"""Сериализатор для работы с промокодами артиста.

Поддерживает процентную и фиксированную скидку.
Поле owner подставляется автоматически из request.user во ViewSet.
"""

from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from store.models import Promocode


class PromocodeSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Promocode."""

    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = Promocode
        fields = (
            'id',
            'code',
            'description',
            'discount_type',
            'discount_value',
            'usage_limit',
            'used_count',
            'start_at',
            'end_at',
            'is_active',
            'is_enabled',
            'is_available',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'used_count',
            'is_active',
            'is_available',
            'created_at',
            'updated_at',
        )

    def validate_code(self, value: str) -> str:
        return value.upper()

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
        discount_type = attrs.get('discount_type') or getattr(
            self.instance,
            'discount_type',
            None,
        )
        discount_value = attrs.get('discount_value')
        if discount_value is None:
            discount_value = getattr(self.instance, 'discount_value', None)

        start_at = (
            attrs.get('start_at')
            if 'start_at' in attrs
            else getattr(self.instance, 'start_at', None)
        )
        end_at = (
            attrs.get('end_at')
            if 'end_at' in attrs
            else getattr(self.instance, 'end_at', None)
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
                'end_at': (
                    'Дата окончания должна быть строго позже даты начала.'
                ),
            })

        return attrs
