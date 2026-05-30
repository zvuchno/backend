"""Модуль админки для модели Cart.

Содержит настройку интерфейса Django Admin для модели корзины пользователя.
"""

from django.contrib import admin
from django.db import models
from django.forms import Textarea
from django.utils.html import format_html

from common.utils.money import format_money

from .forms import MoneyForm
from store.models import Cart, CartItem, ProductVariant
from store.services import CartCalculationService


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    """Регистрация ProductVariant для autocomplete_fields."""

    search_fields = (
        'sku',
        'property_value',
        'product__track__name',
        'product__album__name',
        'product__merch__name',
    )

    def has_module_permission(self, request):
        """Скрываем из главного меню админки."""
        return False


class CartItemInline(admin.TabularInline):
    """Инлайн отображения позиций в корзине."""

    model = CartItem
    form = MoneyForm
    extra = 0
    fields = (
        'product_variant',
        'get_allow_overpay',
        'is_artist_subscription',
        'quantity',
        'get_price',
        'price_with_donation',
        'get_discount',
        'get_line_total',
        'comment',
    )
    autocomplete_fields = ('product_variant',)

    readonly_fields = (
        'get_allow_overpay',
        'get_price',
        'get_discount',
        'get_line_total',
    )

    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 2, 'cols': 30})},
    }

    def get_queryset(self, request):
        """Возвращает оптимизированный кверисет позиций корзины."""
        qs = (
            super()
            .get_queryset(request)
            .with_prices()
            .select_related(
                'cart',
                'product_variant__product',
            )
        )

        # кэш сервисов по cart_id
        self._services = {}

        cart_ids = qs.values_list('cart_id', flat=True).distinct()

        carts = Cart.objects.filter(id__in=cart_ids)

        for cart in carts:
            self._services[cart.id] = CartCalculationService(cart)

        return qs

    def _service(self, obj) -> CartCalculationService | None:
        """Получает CartCalculationService для корзины текущего объекта."""
        return self._services.get(obj.cart_id)

    @admin.display(description='Скидка, руб.')
    def get_discount(self, obj):
        """Возвращает общую сумму скидки для позиции корзины."""
        service = self._service(obj)
        if not service:
            return 0
        return format_money(service.get_item_discounts().get(obj.id, 0))

    @admin.display(description='Сумма, руб.')
    def get_line_total(self, obj):
        """Отображает сумму по позиции с учетом скидки."""
        service = self._service(obj)
        if not service:
            return obj._line_total
        return format_money(service.get_item_line_total(obj))

    @admin.display(description='Цена (руб.)')
    def get_price(self, obj):
        """Проходим цепочку: CartItem -> ProductVariant -> Product -> price."""
        if obj.product_variant and obj.product_variant.product:
            return format_money(obj.product_variant.product.price)
        return None

    @admin.display(description='Разрешена переплата', boolean=True)
    def get_allow_overpay(self, obj):
        """Возвращает флаг разрешения переплаты из связанного продукта."""
        if obj.product_variant and obj.product_variant.product:
            return obj.product_variant.product.allow_overpay
        return None

    def get_formset(self, request, obj=None, **kwargs):
        """Отключаем кнопки управления связанным объектом."""
        formset = super().get_formset(request, obj, **kwargs)
        widget = formset.form.base_fields['product_variant'].widget
        widget.can_add_related = False
        widget.can_change_related = False
        widget.can_view_related = False
        return formset


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """Админка модели Cart с вложенными позициями."""

    list_display = (
        'get_user',
        'get_subtotal',
        'get_discount_promocode',
        'get_total',
    )
    search_fields = ('user__username', 'user__email')
    autocomplete_fields = ('user', 'promocode')
    readonly_fields = (
        'user',
        'get_subtotal',
        'get_discount_promocode',
        'get_total',
        'created_at',
        'updated_at',
    )
    inlines = (CartItemInline,)
    fieldsets = (
        (
            'Основная информация',
            {
                'fields': (
                    'user',
                    'get_subtotal',
                    'get_discount_promocode',
                    'get_total',
                    'promocode',
                ),
            },
        ),
        (
            'Системная информация',
            {
                'classes': ('collapse',),
                'fields': ('created_at', 'updated_at'),
            },
        ),
    )

    def get_queryset(self, request):
        """Возвращает кверисет корзин, кэшируя сервисы расчёта для списка."""
        qs = (
            super()
            .get_queryset(request)
            .with_subtotal()
            .select_related('user', 'promocode')
        )

        self._services = {}

        for cart in qs:
            self._services[cart.id] = CartCalculationService(cart)

        return qs

    def _service(self, obj) -> CartCalculationService | None:
        """Получает CartCalculationService для корзины текущего объекта."""
        return self._services.get(obj.id)

    @admin.display(description='Покупатель')
    def get_user(self, obj):
        if obj.user:
            return obj.user

        return format_html(
            '<span style="color: #C0C0C0; '
            'font-style: italic;">session:</span> [...{}]',
            str(obj.session_key)[:16],
        )

    @admin.display(description='Сумма (руб.)', ordering='_subtotal')
    def get_subtotal(self, obj):
        """Базовая стоимость корзины до применения скидок."""
        return format_money(obj.subtotal)

    @admin.display(description='Сумма скидки по промокоду (руб.)')
    def get_discount_promocode(self, obj):
        """Общая сумма скидки, начисленная по промокоду корзины."""
        service = self._service(obj)
        return format_money(service.get_discount_total() if service else 0)

    @admin.display(description='Итого (руб.)')
    def get_total(self, obj):
        """Финальная стоимость корзины с учётом всех скидок."""
        service = self._service(obj)
        return format_money(service.get_total() if service else obj.subtotal)

    def get_form(self, request, obj=None, **kwargs):
        """Отключает кнопки быстрого создания, изменения и удаления."""
        form = super().get_form(request, obj, **kwargs)

        field = form.base_fields.get('promocode')
        if field and hasattr(field.widget, 'can_change_related'):
            field.widget.can_add_related = False
            field.widget.can_change_related = False
            field.widget.can_delete_related = False
        return form

    def has_add_permission(self, request):
        """Запрещает ручное создание заказов через кнопку 'Добавить'."""
        return False
