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
