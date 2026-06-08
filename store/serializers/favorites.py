"""Сериализатор избранного пользователя."""

from rest_framework import serializers

from .base_variant_list_item import BaseVariantTargetImageSerializer
from store.constants import (
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import Favorite


class FavoriteReadSerializer(BaseVariantTargetImageSerializer):
    """Сериализатор для чтения модели Favorite."""

    product_variant = serializers.IntegerField(
        source='product_variant.id',
        read_only=True,
    )
    name = serializers.CharField(
        source='product_variant.variant_name',
        read_only=True,
    )
    kind = serializers.CharField(
        read_only=True,
        allow_null=True,
        help_text=(
            'Человекочитаемый вид карточки: Альбом, Сингл, '
            'Винил, Футболка, Трек и т.п.'
        ),
    )
    artist_name = serializers.CharField(
        read_only=True,
        allow_null=True,
        help_text='Имя артиста-владельца товара.',
    )
    price = serializers.DecimalField(
        source='unit_price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )

    class Meta(BaseVariantTargetImageSerializer.Meta):
        model = Favorite
        fields = (
            'id',
            'artist_name',
            'name',
            'kind',
            'price',
            'product_variant',
        ) + BaseVariantTargetImageSerializer.Meta.fields
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=Favorite.objects.all(),
                fields=['user', 'product_variant'],
                message='Этот товар уже в вашем избранном.',
            ),
        ]


class FavoriteWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для записи модели Favorite."""

    user = serializers.HiddenField(
        default=serializers.CurrentUserDefault(),
    )

    class Meta:
        model = Favorite
        fields = ('id', 'user', 'product_variant')
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=Favorite.objects.all(),
                fields=['user', 'product_variant'],
                message='Этот товар уже в вашем избранном.',
            ),
        ]
