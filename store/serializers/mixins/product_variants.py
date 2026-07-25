from store.constants import CHAR_PRESET_SIMPLE


class ProductVariantsMixin:
    """Миксин для получения вариантов продукта в унифицированном формате."""

    def get_variants(self, obj) -> list[dict]:
        """Унифицирует формат вариантов для альбома.

        Возвращает список с единственным дефолтным вариантом, чтобы фронтенд
        мог использовать общую логику обработки (как для мерча).
        'value' пустое, так как выбор не требуется.
        """
        product = getattr(obj, 'product', None)
        if not product:
            return []
        variant = product.variants.first()
        if not variant:
            return []

        return [
            {
                'id': variant.id,
                'sku': variant.sku,
                'stock': variant.stock,
                'value': '',
            },
        ]


class ProductVariantSelectionMixin:
    """Миксин для выбора учитываемых вариантов продукта."""

    @staticmethod
    def select_product_variants(product, variants) -> list:
        """Возвращает варианты с учётом настройки свойства продукта."""
        if product.property_name:
            return [
                variant
                for variant in variants
                if variant.property_value != CHAR_PRESET_SIMPLE
            ]

        return [
            variant
            for variant in variants
            if variant.property_value == CHAR_PRESET_SIMPLE
        ]

    @classmethod
    def calculate_product_stock(cls, product, variants) -> int:
        """Возвращает общий остаток учитываемых вариантов."""
        selected_variants = cls.select_product_variants(
            product,
            variants,
        )
        return sum(variant.stock or 0 for variant in selected_variants)
