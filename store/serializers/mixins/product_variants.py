from store.constants import CHAR_PRESET_SIMPLE


class ProductVariantsMixin:
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
