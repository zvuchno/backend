"""Модуль админки для модели Merch.

Содержит настройку интерфейса Django Admin для модели мерча.
"""

from django import forms
from django.contrib import admin
from django.utils.html import format_html
from nested_admin import (
    NestedModelAdmin,  # noqa
    NestedStackedInline,  # noqa
    NestedTabularInline,  # noqa
)

from .forms import (
    MerchImageInlineFormSet,
    MoneyForm,
)
from store.admin.mixins import (
    AutoCreatedByAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
)
from store.models import Image, Merch, Product, ProductVariant
from store.services import MerchImageService


class MerchVariantForm(forms.ModelForm):
    """Форма для инлайна вариантов продукта."""

    class Meta:
        model = ProductVariant
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        """Делает обязательными поля варианта продукта."""
        super().__init__(*args, **kwargs)
        self.fields['property_value'].required = True


class ProductVariantInline(NestedTabularInline):
    """Инлайн для редактирования вариантов продукта в админке."""

    model = ProductVariant
    form = MerchVariantForm
    fields = ('sku', 'property_value', 'stock', 'is_active', 'updated_at')
    extra = 0
    readonly_fields = ('sku', 'updated_at')


class ProductInline(NestedStackedInline):
    """Инлайн продукта с вложенными вариантами."""

    model = Product
    form = MoneyForm
    inlines = (ProductVariantInline,)
    fields = ('price', 'allow_overpay', 'property_name')
    can_delete = False

    def has_delete_permission(self, request, obj=None):
        return False


class PhotoInline(NestedTabularInline):
    """Отображение фото в модели мерча."""

    model = Image
    formset = MerchImageInlineFormSet
    extra = 1
    fields = ('image', 'preview', 'is_main')
    readonly_fields = ('preview',)

    @admin.display(description='Превью')
    def preview(self, image):
        if image.image:
            return format_html(
                '<img src="{}" style="height:60px; border-radius:4px"/>',
                image.image.url,
            )
        return '-'


@admin.register(Merch)
class MerchAdmin(
    AutoCreatedByAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
    NestedModelAdmin,
):
    """Админка мерча."""

    inlines = (PhotoInline, ProductInline)
    list_display = (
        'name',
        'kind',
        'artist',
        'payout_recipient',
        'image_preview',
        'album',
        'is_published',
        'get_price',
        'get_allow_overpay',
        'visibility',
        'is_active',
    )
    list_editable = (
        'is_active',
        'is_published',
        'visibility',
    )
    list_filter = (
        'is_active',
        'created_at',
        'updated_at',
        'visibility',
        'kind',
    )
    search_fields = (
        'name',
        'kind__name',
        'artist__name',
        'payout_recipient__email',
        'created_by__email',
        'album__name',
    )
    ordering = ('-created_at',)
    search_help_text = (
        'Поиск по названию, типу, артисту, альбому, '
        'получателю выплат и создателю'
    )

    def get_readonly_fields(self, request, obj=None):
        """Возвращает поля, недоступные для ручного изменения."""
        readonly_fields = (
            *super().get_readonly_fields(request, obj),
            'image_preview',
            'display_is_carrier',
            'created_at',
            'updated_at',
            'payout_recipient',
            'created_by',
        )

        if obj is not None:
            readonly_fields += ('artist',)

        return readonly_fields

    autocomplete_fields = ('album', 'artist', 'kind')

    fieldsets = (
        (
            'Основная информация',
            {
                'fields': (
                    'kind',
                    'name',
                    'display_is_carrier',
                    'description',
                    'image_preview',
                    'album',
                    'is_published',
                    'visibility',
                    'artist',
                    'payout_recipient',
                    'is_active',
                ),
            },
        ),
        (
            'Системная информация',
            {
                'classes': ('collapse',),
                'fields': (
                    'created_at',
                    'updated_at',
                    'created_by',
                ),
            },
        ),
    )

    @admin.display(description='Носитель', boolean=True)
    def display_is_carrier(self, obj):
        """Отображает статус носителя для мерча."""
        return obj.is_carrier

    def get_queryset(self, request):
        qs = super(NestedModelAdmin, self).get_queryset(request)
        return qs.select_related(
            'product',
            'kind',
            'artist',
            'payout_recipient',
            'created_by',
            'album',
        ).prefetch_related(
            'images_merch',
            'product__variants',
        )

    def save_model(self, request, obj, form, change):
        """Сохраняет мерч и назначает получателя выплат."""
        if not change and obj.payout_recipient_id is None:
            obj.payout_recipient = obj.artist.default_payout_recipient

        super().save_model(request, obj, form, change)

    @admin.display(description='Главное фото')
    def image_preview(self, obj):
        images = list(obj.images_merch.all())

        for image in images:
            if image.is_main:
                return format_html(
                    '<img src="{}" style="max-height:100px; width:auto;" />',
                    image.image.url,
                )

        image = images[0] if images else None
        if image:
            return format_html(
                '<img src="{}" style="max-height:100px; width:auto;" />',
                image.image.url,
            )
        return '-'

    def save_related(self, request, form, formsets, change):
        """Сохраняет связанные объекты и нормализует главное фото."""
        super().save_related(request, form, formsets, change)

        MerchImageService.ensure_main_image(
            merch=form.instance,
        )
