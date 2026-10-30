"""Админка треков релизов."""

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction

from ..services import get_track_sales_stats, tracks_have_sales
from .forms import MoneyForm, TrackDeactivationProtectionMixin
from .mixins import (
    CommerceBaseMixin,
    CommerceDisplayMixin,
)
from .recording import RecordingAdmin as RecordingAdmin
from .recording import (
    RecordingReleaseTrackInline as RecordingReleaseTrackInline,
)
from .recording import TrackGeneratedAudioInline as TrackGeneratedAudioInline
from store.models import (
    Album,
    Product,
    ReleaseTrack,
)
from store.services.album_archive import AlbumArchiveScheduler
from store.services.album_publication import unpublish_if_empty


class ProductInline(admin.StackedInline):
    """Инлайн для редактирования полей продукта, связанных с треком."""

    model = Product
    form = MoneyForm
    fields = ('price', 'allow_overpay')
    can_delete = False
    verbose_name = 'Торговые настройки трека'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('track')


class TrackAdminForm(
    TrackDeactivationProtectionMixin,
    forms.ModelForm,
):
    """Форма трека релиза с защитой приобретённого контента."""

    class Meta:
        model = ReleaseTrack
        fields = '__all__'


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
