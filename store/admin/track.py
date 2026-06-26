"""Модуль админки для модели Track.

Содержит настройку интерфейса Django Admin для модели музыкального трека.
"""

from django.contrib import admin

from ..services.audio.shedule import TrackGeneratedAudioScheduler
from .forms import MoneyForm
from .mixins import (
    AutoOwnerAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
)
from store.models import Product, Track, TrackGeneratedAudio


class ProductInline(admin.StackedInline):
    """Инлайн для редактирования полей продукта, связанных с треком."""

    model = Product
    form = MoneyForm
    fields = ('price', 'allow_overpay')
    can_delete = False
    verbose_name = 'Торговые настройки трека'


class TrackGeneratedAudioInline(admin.StackedInline):
    """Инлайн результатов фоновой подготовки аудиофайлов."""

    model = TrackGeneratedAudio
    extra = 0
    max_num = 1
    can_delete = False
    verbose_name = 'Сгенерированные аудиофайлы'
    verbose_name_plural = 'Сгенерированные аудиофайлы'

    fields = (
        'preview_file',
        'preview_duration',
        'preview_status',
        'preview_error',
        'preview_started_at',
        'stream_file',
        'stream_status',
        'stream_error',
        'stream_started_at',
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        """Запрещает ручное создание результатов обработки."""
        return False

    def has_change_permission(self, request, obj=None):
        """Запрещает ручное изменение результатов обработки."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрещает ручное удаление результатов обработки."""
        return False


@admin.register(Track)
class TrackAdmin(
    AutoOwnerAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
    admin.ModelAdmin,
):
    """Админка для модели Track."""

    list_display = (
        'name',
        'album',
        'owner',
        'get_price',
        'get_allow_overpay',
        'is_active',
    )
    search_fields = ('album__name', 'description', 'name')
    list_filter = (
        'is_active',
        'created_at',
        'updated_at',
    )
    ordering = ('album', 'position')
    readonly_fields = (
        'formatted_duration',
        'duration',
        'created_at',
        'updated_at',
        'get_sku',
        'owner',
    )
    list_editable = ('is_active',)
    fieldsets = (
        (
            'Основная информация',
            {
                'fields': (
                    'name',
                    'album',
                    'is_active',
                    'audio_file',
                    'formatted_duration',
                    'description',
                    'get_sku',
                    'owner',
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
    inlines = (ProductInline, TrackGeneratedAudioInline)

    @admin.display(description='Длительность')
    def formatted_duration(self, obj):
        """Показывает длительность трека в формате мм:сс."""
        if obj.duration is None:
            return '-'
        minutes = obj.duration // 60
        seconds = obj.duration % 60
        return f'{minutes}:{seconds:02}'

    def get_queryset(self, request):
        """Родительский метод миксина + select_related('album', 'owner')."""
        return super().get_queryset(request).select_related('album', 'owner')

    def save_model(self, request, obj, form, change):
        """Сохраняет трек и запускает обработку при изменении исходника."""
        super().save_model(request, obj, form, change)
        if not change or 'audio_file' in form.changed_data:
            TrackGeneratedAudioScheduler.schedule(obj)
