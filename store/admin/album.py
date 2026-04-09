"""Модуль админки для модели Album.

Содержит настройку интерфейса Django Admin для модели альбомов.
"""

from decimal import Decimal

from django import forms
from django.contrib import admin
from django.core.validators import MinValueValidator
from django.db import transaction
from django.utils.html import format_html
from nested_admin import (
    NestedModelAdmin,
    NestedStackedInline,
    NestedTabularInline,
)

from .mixins import (
    AutoOwnerAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
)
from store.constants import (
    MAX_PRICE_DIGITS,
    PRICE_DECIMAL_PLACES,
)
from store.models import Album, Product, Track


class TrackInlineForm(forms.ModelForm):
    """Форма для TrackInline с редактированием цены из связанного Product.

    Особенности:
    - Добавляет виртуальное поле 'price', которого нет в модели Track.
    Оно отображает и редактирует 'Product.price'.
    - Цепочка save_m2m сохраняет существующую логику других inline-форм.
    - Использует атомарную транзакцию при сохранении цены.
    """

    price = forms.DecimalField(
        label='Цена',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        validators=[MinValueValidator(Decimal('0.00'))],
        initial=Decimal('0.00'),
        required=False,
    )

    class Meta:
        model = Track
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        """Инициализация формы с подстановкой цены из связанного Product."""
        super().__init__(*args, **kwargs)

        product = getattr(self.instance, 'product', None)

        if product:
            # Если Product существует, подставляем его цену в initial
            self.fields['price'].initial = product.price

    def save(self, commit=True):
        """Сохраняет Track и синхронизирует цену с Product.

        Особенности:
        - создаёт Product, если его нет.
        - обновляет цену, только если пользователь ввёл новое значение.
        - Если commit=True, вызываем sync_price сразу.
        - Если commit=False, цепляем sync_price к save_m2m,
        сохраняя существующую логику.
        """
        # Сохраняем Track (может быть commit=False)
        instance = super().save(commit=commit)
        # Берём цену из формы, 0.00 если поле пустое
        price = self.cleaned_data.get('price') or Decimal('0.00')

        @transaction.atomic
        def sync_price() -> None:
            """Функция синхронизации цены с Product."""
            product, _ = Product.objects.get_or_create(track=instance)
            if price is not None and product.price != price:
                product.price = price
                # Сохраняем только поле price
                product.save(update_fields=['price'])

        if commit:
            # Для обычного сохранения вызываем сразу
            sync_price()
        else:
            # Для inline-форм в админке: цепляем к save_m2m
            original_save_m2m = getattr(self, 'save_m2m', None)

            def chained_save_m2m() -> None:
                # Сначала вызываем существующий save_m2m, если есть
                if original_save_m2m:
                    original_save_m2m()
                # Затем синхронизируем цену
                sync_price()

            self.save_m2m = chained_save_m2m
        return instance


class TrackInline(NestedTabularInline):
    """Инлайн для списка треков (модель Track)."""

    model = Track
    form = TrackInlineForm
    fields = (
        'position',
        'name',
        'audio_file',
        'duration',
        'is_active',
        'price',
    )
    readonly_fields = ('duration',)
    extra = 0  # Чтобы Nested-сортировка не требовала заполнять пустое поле
    show_change_link = True
    ordering = ('position',)
    sortable_field_name = 'position'

    def get_queryset(self, request):
        """Подтянуть связанные с Track поля."""
        qs = super().get_queryset(request)
        return qs.select_related('product')


class ProductInline(NestedStackedInline):
    """Инлайн продукта с вложенными вариантами."""

    model = Product
    fields = ('price', 'allow_overpay')
    can_delete = False
    verbose_name = 'Торговые настройки альбома'


@admin.register(Album)
class AlbumAdmin(
    AutoOwnerAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
    NestedModelAdmin,
):
    """Админка модели Album с поддержкой вложенных inline.

    Отображает:
    - Основные поля альбома.
    - Инлайн Product и его варианты (ProductInline).
    - Инлайн Track (TrackInline).

    Особенности:
    - Переход на NestedModelAdmin позволяет редактировать вложенные объекты
      прямо в форме альбома.
    """

    list_display = (
        'name',
        'genre',
        'owner',
        'is_single',
        'is_published',
        'get_price',
        'get_allow_overpay',
        'visibility',
        'is_active',
    )
    search_fields = ('genre__name', 'name')
    list_filter = (
        'is_active',
        'created_at',
        'updated_at',
        'visibility',
    )
    ordering = ('-created_at', 'is_active', 'name')
    readonly_fields = (
        'image_preview',
        'created_at',
        'updated_at',
        'get_sku',
        'owner',
    )
    list_editable = ('is_active', 'is_published', 'visibility')
    fieldsets = (
        (
            'Основные данные',
            {
                'fields': (
                    'name',
                    'genre',
                    'is_single',
                    'release_date',
                    'description',
                    'cover_image',
                    'image_preview',
                    'is_published',
                    'visibility',
                    'get_sku',
                    'owner',
                    'created_at',
                    'updated_at',
                    'is_active',
                ),
            },
        ),
    )
    inlines = (ProductInline, TrackInline)

    @admin.display(description='Изображение')
    def image_preview(self, obj):
        """Возвращает HTML-превью обложки альбома в списке админки."""
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="height:100px;border-radius:4px;">',
                obj.cover_image.url,
            )
        return '-'

    def get_queryset(self, request):
        """Родительский метод миксина + select_related('genre', 'owner')."""
        return super().get_queryset(request).select_related('genre', 'owner')
