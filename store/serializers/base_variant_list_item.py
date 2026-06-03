from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from store.serializers.catalog_card import (
    CatalogCardTargetSerializer,
    VariantKeySerializer,
)


class BaseVariantListItemSerializer(serializers.ModelSerializer):
    """Базовый сериализатор элемента списка, связанного с ProductVariant.

    Применяется для list-эндпоинтов (корзина, избранное, заказы),
    где объект представлен как элемент списка товаров с логикой перехода.

    Добавляет общие поля представления:
    - target: данные для перехода на целевую сущность (album / merch)
    - selected_variant_key: ключ варианта для предвыбора на странице detail
    """

    target = serializers.SerializerMethodField(
        help_text=(
            'Данные для перехода по клику. '
            'Например, карточка носителя может вести на detail альбома.'
        ),
        read_only=True,
    )

    selected_variant_key = serializers.SerializerMethodField(
        help_text=(
            'Ключ варианта, который предвыбрать после перехода в detail.'
        ),
        read_only=True,
    )

    @extend_schema_field(CatalogCardTargetSerializer)
    def get_target(self, obj):
        """Возвращает данные для перехода из карточки товара."""
        return {
            'type': obj.target_type,
            'url': self.get_target_url(obj),
        }

    @extend_schema_field(VariantKeySerializer)
    def get_selected_variant_key(self, obj):
        """Возвращает ключ для предвыбора варианта."""
        content = getattr(obj.product_variant.product, 'content', None)
        if content is None:
            return None

        return {
            'type': obj.product_variant.product.product_type,
            'id': obj.product_variant_id,
        }
