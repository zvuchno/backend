"""Админка музыкальных мастер-записей."""

from django.contrib import admin
from django.db import transaction
from django.utils.html import format_html

from .mixins import AutoCreatedByAdminMixin
from store.models import Recording, ReleaseTrack, TrackGeneratedAudio
from store.services.audio.schedule import TrackGeneratedAudioScheduler


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
