"""Миксины админки Django для моделей Album, Track, Merch."""

from django.contrib import admin

from common.utils.money import format_money

from store.constants import CHAR_PRESET_SIMPLE
from store.models import ProductVariant
from store.services import ProductService


class CommerceBaseMixin:
    """Миксин для ModelAdmin, обеспечивающий целостность коммерческих данных.

    Гарантирует наличие связанных объектов Product
    и Variant через ProductService.
    """

    def save_related(self, request, form, formsets, change):
        """Обеспечивает создание коммерческой инфраструктуры после сохранения.

        Метод извлекает данные о вариантах из вложенных формсетов админки,
        структурирует их и передает в ProductService. Это гарантирует,
        что при создании мерча в админке автоматически создадутся
        соответствующие объекты Product и ProductVariant.
        """
        super().save_related(request, form, formsets, change)

        # Собираем данные для сервиса
        validated_data = form.cleaned_data.copy()

        # Ищем формсет с вариантами
        for formset in formsets:
            if formset.model.__name__ == 'ProductVariant':
                active_variants = []

                for sub_form in formset.forms:
                    if not sub_form.cleaned_data:
                        continue

                    data = sub_form.cleaned_data.copy()
                    is_deleted = data.get('DELETE', False)
                    is_active = data.get('is_active', True)
                    val = data.get('property_value')
                    is_simple = val and str(val).strip() == CHAR_PRESET_SIMPLE

                    if is_simple and not is_deleted:
                        validated_data['stock'] = data.get('stock') or 0

                    if is_deleted or not is_active or is_simple:
                        continue

                    if isinstance(data.get('id'), ProductVariant):
                        data['id'] = data['id'].pk
                    elif hasattr(data.get('id'), 'pk'):
                        data['id'] = data['id'].pk

                    active_variants.append(data)

                validated_data['variants'] = (
                    active_variants if active_variants else None
                )

        ProductService.ensure_commerce(
            form.instance,
            validated_data=validated_data,
        )


class CommerceDisplayMixin:
    """Методы отображения коммерческих данных и оптимизация запросов.

    Особенности:
    - Предоставляет геттеры для 'price', 'sku' и 'allow_overpay'.
    - Оптимизирует get_queryset через select_related('product')
      и prefetch_related('product__variants').
    """

    @admin.display(description='Цена')
    def get_price(self, obj):
        """Геттер для отображения поля price из связанного Product."""
        product = getattr(obj, 'product', None)
        return format_money(product.price) if product else '-'

    @admin.display(description='Переплата', boolean=True)
    def get_allow_overpay(self, obj):
        """Геттер для отображения поля allow_overpay из связанного Product."""
        product = getattr(obj, 'product', None)
        return product.allow_overpay if product else False

    @admin.display(description='SKU', empty_value='-')
    def get_sku(self, obj):
        """Геттер для отображения поля sku из связанного ProductVariant."""
        product = getattr(obj, 'product', None)
        if not product:
            return None
        # Из кэша prefetch_related..
        variants = list(product.variants.all())
        return variants[0].sku if variants else None

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('product')
            .prefetch_related('product__variants')
        )
