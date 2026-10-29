"""Админка музыкальных записей и треков релизов."""

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.html import format_html

from ..services import get_track_sales_stats, tracks_have_sales
from .forms import MoneyForm, TrackDeactivationProtectionMixin
from .mixins import (
    AutoCreatedByAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
)
from store.models import (
    Album,
    Product,
    Recording,
    ReleaseTrack,
    TrackGeneratedAudio,
)
from store.services.album_archive import AlbumArchiveScheduler
from store.services.album_publication import unpublish_if_empty
from store.services.audio.schedule import TrackGeneratedAudioScheduler


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


class TrackAdminForm(
    TrackDeactivationProtectionMixin,
    forms.ModelForm,
):
    """Форма трека релиза с защитой приобретённого контента."""

    class Meta:
        model = ReleaseTrack
        fields = '__all__'


class RecordingReleaseTrackInline(admin.TabularInline):
    """Показывает релизы, в которых используется мастер-запись."""

    model = ReleaseTrack
    fk_name = 'recording'
    fields = (
        'release',
        'position',
        'is_active',
    )
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Recording)
class RecordingAdmin(
    AutoCreatedByAdminMixin,
    admin.ModelAdmin,
):
    """Админка мастер-записей."""

    list_display = (
        'name',
        'owner',
        'isrc',
        'formatted_duration',
        'is_active',
    )
    search_fields = (
        'name',
        'description',
        'isrc',
        'owner__name',
    )
    list_filter = (
        'is_active',
        'created_at',
        'updated_at',
    )
    ordering = ('name', 'id')
    readonly_fields = (
        'formatted_duration',
        'duration',
        'file_hash',
        'created_at',
        'updated_at',
        'created_by',
    )
    fieldsets = (
        (
            'Основная информация',
            {
                'fields': (
                    'name',
                    'owner',
                    'isrc',
                    'is_active',
                    'audio_file',
                    'formatted_duration',
                    'description',
                ),
            },
        ),
        (
            'Системная информация',
            {
                'classes': ('collapse',),
                'fields': (
                    'file_hash',
                    'created_at',
                    'updated_at',
                    'created_by',
                ),
            },
        ),
    )

    inlines = (
        RecordingReleaseTrackInline,
        TrackGeneratedAudioInline,
    )

    @admin.display(description='Длительность')
    def formatted_duration(self, obj):
        """Показывает длительность трека в формате мм:сс."""
        if obj.duration is None:
            return '-'
        minutes = obj.duration // 60
        seconds = obj.duration % 60
        return f'{minutes}:{seconds:02}'

    def get_queryset(self, request):
        """Возвращает записи с владельцем и создателем."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                'owner',
                'created_by',
            )
        )

    def save_model(self, request, obj, form, change):
        """Сохраняет мастер-запись и запускает обработку исходного аудио."""
        should_schedule_audio = not change or 'audio_file' in form.changed_data

        with transaction.atomic():
            if should_schedule_audio:
                obj.file_hash = ''

            super().save_model(request, obj, form, change)

            if should_schedule_audio:
                transaction.on_commit(
                    lambda: TrackGeneratedAudioScheduler.schedule(obj),
                )

    def has_delete_permission(self, request, obj=None):
        """Запрещает физическое удаление мастер-записей."""
        return False


@admin.register(ReleaseTrack)
class ReleaseTrackAdmin(
    CommerceBaseMixin,
    CommerceDisplayMixin,
    admin.ModelAdmin,
):
    """Админка размещений музыкальных записей в релизах."""

    form = TrackAdminForm

    list_display = (
        'name',
        'release',
        'position',
        'recording',
        'artist',
        'payout_recipient',
        'get_price',
        'get_allow_overpay',
        'is_active',
    )
    search_fields = (
        'recording__name',
        'recording__isrc',
        'release__name',
        'release__artist__name',
    )
    list_filter = (
        'is_active',
        'created_at',
        'updated_at',
    )
    ordering = (
        'release',
        'position',
        'id',
    )
    readonly_fields = (
        'release',
        'recording',
        'artist',
        'payout_recipient',
        'created_at',
        'updated_at',
    )
    fieldsets = (
        (
            'Трек релиза',
            {
                'fields': (
                    'release',
                    'recording',
                    'position',
                    'is_active',
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
                ),
            },
        ),
    )
    inlines = (ProductInline,)

    def save_model(self, request, obj, form, change):
        """Сохраняет размещение и актуализирует состояние релиза."""
        should_schedule_archive = change and 'is_active' in form.changed_data

        with transaction.atomic():
            super().save_model(request, obj, form, change)
            unpublish_if_empty(obj.release)

            if should_schedule_archive:
                transaction.on_commit(
                    lambda: AlbumArchiveScheduler.schedule_by_id(
                        obj.release_id,
                    ),
                )

    def get_queryset(self, request):
        """Возвращает треки с релизом, записью и коммерческими данными."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                'recording',
                'release',
                'release__artist',
                'release__payout_recipient',
                'product',
            )
        )

    def delete_model(self, request, obj):
        """Удаляет размещение и актуализирует состояние релиза."""
        sales = get_track_sales_stats(obj)

        if sales.total_sales:
            raise ValidationError(
                (
                    'Нельзя физически удалить трек с историей приобретения. '
                    f'Трек куплен отдельно: {sales.direct_sales} раз; '
                    f'в составе релиза: {sales.release_sales} раз. '
                    'Чтобы изменить состав, снимите текущий релиз с продажи '
                    'и создайте новый без этого трека.'
                ),
            )

        release_id = obj.release_id

        with transaction.atomic():
            super().delete_model(request, obj)

            release = Album.objects.get(pk=release_id)
            unpublish_if_empty(release)

            transaction.on_commit(
                lambda: AlbumArchiveScheduler.schedule_by_id(release_id),
            )

    def delete_queryset(self, request, queryset):
        """Удаляет только треки без истории приобретения."""
        if tracks_have_sales(queryset):
            raise ValidationError(
                'Среди выбранных треков есть треки с историей приобретения. '
                'Их нельзя физически удалить.',
            )

        release_ids = set(
            queryset.values_list('release_id', flat=True),
        )

        with transaction.atomic():
            super().delete_queryset(request, queryset)

            for release in Album.objects.filter(pk__in=release_ids):
                unpublish_if_empty(release)
                release_id = release.pk

                transaction.on_commit(
                    lambda release_id=release_id: (
                        AlbumArchiveScheduler.schedule_by_id(release_id)
                    ),
                )

    def has_delete_permission(self, request, obj=None):
        """Запрещает удаление трека с историей приобретения."""
        if obj is not None and get_track_sales_stats(obj).total_sales:
            return False

        return super().has_delete_permission(request, obj)

    def has_add_permission(self, request, obj=None):
        """Создание размещений выполняется только через TrackService."""
        return False
