"""Сериализатор для работы с промокодами артистов и лейблов.

Поддерживают процентные и фиксированные скидки.
При создании промокод связывается с выбранным управляемым профилем артиста,
а пользователь-создатель сохраняется в поле created_by во ViewSet.
"""

from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .mixins import ImmutableFieldsSerializerMixin
from store.constants import (
    DISCOUNT_VALUE_PRECISION,
    MAX_PRICE_DIGITS,
    MAX_PROMOCODE_LENGTH,
    ZERO_MONEY,
)
from store.models import Promocode
from store.validators import (
    validate_promocode_format,
    validate_promocode_min_length,
)
from users.models import ArtistProfile


class PromocodeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Promocode."""

    class Meta:
        model = Promocode
        fields = (
            'id',
            'artist',
            'code',
            'discount_value',
            'discount_type',
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
        fields = PromocodeReadSerializer.Meta.fields + ('description',)


class PromocodeWriteSerializer(
    ImmutableFieldsSerializerMixin,
    serializers.ModelSerializer,
):
    """Сериализатор для создания и обновления Promocode."""

    immutable_fields = ('artist', 'code')

    code = serializers.CharField(
        max_length=MAX_PROMOCODE_LENGTH,
        required=True,
        validators=[
            validate_promocode_min_length,
            validate_promocode_format,
            UniqueValidator(
                queryset=Promocode.objects.all(),
                message='Этот код уже занят.',
            ),
        ],
    )
    artist = serializers.PrimaryKeyRelatedField(
        queryset=ArtistProfile.objects.filter(is_active=True),
        required=False,
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
            'artist',
            'description',
            'usage_limit',
            'discount_type',
            'discount_value',
            'start_at',
            'end_at',
            'is_enabled',
        )

    def validate_start_at(self, value):
        if (
            self.instance is None
            and value is not None
            and value.date() < timezone.localdate()
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

        if discount_value is not None and discount_value <= ZERO_MONEY:
            raise serializers.ValidationError({
                'discount_value': ('Скидка должна быть больше 0.'),
            })

        if start_at and end_at and start_at >= end_at:
            raise serializers.ValidationError({
                'end_at': ('Дата окончания должна быть позже даты начала.'),
            })

        return attrs
