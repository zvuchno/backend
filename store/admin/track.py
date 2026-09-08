"""Модуль админки для модели Track.

Содержит настройку интерфейса Django Admin для модели музыкального трека.
TODO: позже перевести замену audio_file в админке на direct upload.
"""

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils.html import format_html

from .forms import MoneyForm
from .mixins import (
    AutoCreatedByAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
)
from store.models import (
    Album,
    Order,
    OrderItem,
    Payment,
    Product,
    Track,
    TrackGeneratedAudio,
)
from store.services.album_archive import AlbumArchiveScheduler
from store.services.album_publication import unpublish_if_empty
from store.services.audio.schedule import TrackGeneratedAudioScheduler


def tracks_were_purchased(queryset) -> bool:
    """Проверяет, есть ли история приобретения у переданных треков."""
    track_ids = queryset.values_list('id', flat=True)
    album_ids = queryset.values_list('album_id', flat=True)

    return (
        OrderItem.objects
        .filter(
            Q(order__status=Order.Status.PAID)
            | Q(
                order__payments__status=Payment.PaymentStatus.SUCCEEDED,
            ),
        )
        .filter(
            Q(product_variant__product__track_id__in=track_ids)
            | Q(product_variant__product__album_id__in=album_ids),
        )
        .exists()
    )


def track_was_purchased(track: Track) -> bool:
    """Проверяет наличие истории приобретения трека."""
    return tracks_were_purchased(
        Track.objects.filter(pk=track.pk),
    )


class ProductInline(admin.StackedInline):
    """Инлайн для редактирования полей продукта, связанных с треком."""

    model = Product
    form = MoneyForm
    fields = ('price', 'allow_overpay')
    can_delete = False
    verbose_name = 'Торговые настройки трека'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('track')


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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('track')

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

    autocomplete_fields = ('album',)

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
        should_schedule_audio = not change or 'audio_file' in form.changed_data
        should_schedule_archive = change and 'is_active' in form.changed_data

        with transaction.atomic():
            super().save_model(request, obj, form, change)
            unpublish_if_empty(obj.album)

            if should_schedule_audio:
                transaction.on_commit(
                    lambda: TrackGeneratedAudioScheduler.schedule(obj),
                )

            if should_schedule_archive:
                album_id = obj.album_id
                transaction.on_commit(
                    lambda: AlbumArchiveScheduler.schedule_by_id(album_id),
                )

    def delete_model(self, request, obj):
        """Удаляет трек и актуализирует состояние альбома."""
        if track_was_purchased(obj):
            raise ValidationError(
                'Нельзя физически удалить ранее приобретённый трек. '
                'Деактивируйте его.',
            )

        album_id = obj.album_id

        with transaction.atomic():
            super().delete_model(request, obj)

            album = Album.objects.get(pk=album_id)
            unpublish_if_empty(album)

            transaction.on_commit(
                lambda: AlbumArchiveScheduler.schedule_by_id(album_id),
            )

    def delete_queryset(self, request, queryset):
        """Удаляет только треки без истории приобретения."""
        if tracks_were_purchased(queryset):
            raise ValidationError(
                'Нельзя физически удалить ранее приобретённые треки. '
                'Деактивируйте их.',
            )

        album_ids = set(queryset.values_list('album_id', flat=True))

        with transaction.atomic():
            super().delete_queryset(request, queryset)

            for album in Album.objects.filter(pk__in=album_ids):
                unpublish_if_empty(album)
                album_id = album.pk
                transaction.on_commit(
                    lambda album_id=album_id: (
                        AlbumArchiveScheduler.schedule_by_id(album_id)
                    ),
                )

    def has_delete_permission(self, request, obj=None):
        """Запрещает удаление трека с историей приобретения."""
        if obj is not None and track_was_purchased(obj):
            return False

        return super().has_delete_permission(request, obj)
