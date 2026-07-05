"""Модуль админки для модели Album.

Содержит настройку интерфейса Django Admin для модели альбомов.
"""

from decimal import ROUND_HALF_UP, Decimal

from django import forms
from django.contrib import admin
from django.core.validators import MinValueValidator
from django.utils.html import format_html
from nested_admin.nested import (
    NestedModelAdmin,
    NestedStackedInline,
    NestedTabularInline,
)

from .forms import MoneyForm
from .mixins import (
    AutoOwnerAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
)
from store.constants import (
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import Album, AlbumArchive, Product, Track
from store.services import ProductService
from store.services.audio import TrackGeneratedAudioScheduler


class TrackInlineForm(MoneyForm):
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
        decimal_places=MONEY_DISPLAY_PRECISION,
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
            self.fields['price'].initial = product.price.quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP,
            )

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
        audio_file_changed = 'audio_file' in self.changed_data

        def sync_related_data() -> None:
            """Синхронизирует коммерческие данные через ProductService.

            И запускает обработку аудио.
            """
            validated_data = {
                'price': price,
                'variants': [],
            }
            ProductService.ensure_commerce(
                instance,
                validated_data=validated_data,
            )
            if audio_file_changed:
                TrackGeneratedAudioScheduler.schedule(instance)

        if commit:
            # Для обычного сохранения вызываем сразу
            sync_related_data()
        else:
            # Для inline-форм в админке: цепляем к save_m2m
            original_save_m2m = getattr(self, 'save_m2m', None)

            def chained_save_m2m() -> None:
                # Сначала вызываем существующий save_m2m, если есть
                if original_save_m2m:
                    original_save_m2m()
                # Затем синхронизируем цену и аудио
                sync_related_data()

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
    form = MoneyForm
    fields = ('price', 'allow_overpay')
    can_delete = False
    verbose_name = 'Торговые настройки альбома'


class AlbumArchiveInline(NestedStackedInline):
    """Инлайн подготовленного архива альбома."""

    model = AlbumArchive
    can_delete = False
    extra = 0
    max_num = 1
    fields = (
        'file',
        'status',
        'content_hash',
        'pending_hash',
        'error_message',
        'created_at',
        'updated_at',
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        """Запрещает ручное создание архива через админку."""
        return False

    def has_change_permission(self, request, obj=None):
        """Запрещает ручное редактирование архива через админку."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрещает ручное удаление архива через админку."""
        return False


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
            'Основная информация',
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
                ),
            },
        ),
    )
    inlines = (ProductInline, TrackInline, AlbumArchiveInline)

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
