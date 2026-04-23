"""Общие инлайны для вариантов продукта в админке."""

from nested_admin import (
    NestedStackedInline,
    NestedTabularInline,
)

from store.models import Product, ProductVariant


class ProductVariantInline(NestedTabularInline):
    """Инлайн для редактирования вариантов продукта в админке."""

    model = ProductVariant
    fields = ('sku', 'property_value', 'stock', 'updated_at')
    extra = 0
    readonly_fields = ('sku', 'updated_at')


class ProductInline(NestedStackedInline):
    """Инлайн продукта с вложенными вариантами."""

    model = Product
    inlines = (ProductVariantInline,)
    fields = ('price', 'allow_overpay')
    can_delete = False

    def has_delete_permission(self, request, obj=None):
        return False
