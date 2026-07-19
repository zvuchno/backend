"""Модуль админки для модели Track.

Содержит настройку интерфейса Django Admin для модели музыкального трека.
TODO: позже перевести замену audio_file в админке на direct upload.
"""

from django.contrib import admin
from django.utils.html import format_html

from ..services.audio.schedule import TrackGeneratedAudioScheduler
from .forms import MoneyForm
from .mixins import (
    AutoCreatedByAdminMixin,
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
        'preview_player',
        'preview_duration',
        'preview_status',
        'preview_error',
        'preview_started_at',
        'stream_file',
        'stream_player',
        'stream_status',
        'stream_error',
        'stream_started_at',
    )
    readonly_fields = fields

    @admin.display(description='Прослушать превью')
    def preview_player(self, obj):
        """Показывает плеер подготовленного превью."""
        if obj.preview_status == TrackGeneratedAudio.ProcessingStatus.FAILED:
            return format_html(
                '<span class="errornote">Ошибка: {}</span>',
                obj.preview_error or 'подробности в логах',
            )

        if obj.preview_status != TrackGeneratedAudio.ProcessingStatus.READY:
            return obj.get_preview_status_display()

        if not obj.preview_file:
            return 'Файл не создан'

        return format_html(
            '<audio controls preload="metadata" src="{}"></audio>',
            obj.preview_file.url,
        )

    @admin.display(description='Прослушать stream')
    def stream_player(self, obj):
        """Показывает плеер подготовленного stream-файла."""
        if obj.stream_status == TrackGeneratedAudio.ProcessingStatus.FAILED:
            return format_html(
                '<span class="errornote">Ошибка: {}</span>',
                obj.stream_error or 'подробности в логах',
            )

        if obj.stream_status != TrackGeneratedAudio.ProcessingStatus.READY:
            return obj.get_stream_status_display()

        if not obj.stream_file:
            return 'Файл не создан'

        return format_html(
            '<audio controls preload="metadata" src="{}"></audio>',
            obj.stream_file.url,
        )

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
    AutoCreatedByAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
    admin.ModelAdmin,
):
    """Админка для модели Track."""

    list_display = (
        'name',
        'album',
        'artist',
        'payout_recipient',
        'get_price',
        'get_allow_overpay',
        'is_active',
    )
    search_fields = (
        'album__name',
        'album__artist__name',
        'album__payout_recipient__email',
        'description',
        'name',
    )
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
        'created_by',
        'get_sku',
        'artist',
        'payout_recipient',
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
                    'artist',
                    'payout_recipient',
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
    inlines = (ProductInline, TrackGeneratedAudioInline)

    @admin.display(
        description='Артист',
        ordering='album__artist__name',
    )
    def artist(self, obj):
        """Возвращает артиста альбома."""
        return obj.album.artist

    @admin.display(
        description='Получатель выплат',
        ordering='album__payout_recipient__email',
    )
    def payout_recipient(self, obj):
        """Возвращает получателя выплат альбома."""
        return obj.album.payout_recipient

    @admin.display(description='Длительность')
    def formatted_duration(self, obj):
        """Показывает длительность трека в формате мм:сс."""
        if obj.duration is None:
            return '-'
        minutes = obj.duration // 60
        seconds = obj.duration % 60
        return f'{minutes}:{seconds:02}'

    def get_queryset(self, request):
        """Возвращает треки с альбомом, владельцем и профилем артиста."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                'album',
                'album__artist',
                'album__payout_recipient',
                'created_by',
            )
        )

    def save_model(self, request, obj, form, change):
        """Сохраняет трек и запускает обработку при изменении исходника."""
        super().save_model(request, obj, form, change)
        if not change or 'audio_file' in form.changed_data:
            TrackGeneratedAudioScheduler.schedule(obj)
