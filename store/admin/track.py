"""Модуль админки для модели Track.

Содержит настройку интерфейса Django Admin для модели музыкального трека.
"""

from django.contrib import admin

from .mixins import AutoOwnerAdminMixin
from store.models import Track


@admin.register(Track)
class TrackAdmin(AutoOwnerAdminMixin, admin.ModelAdmin):
    """Админка для модели Track."""

    list_display = (
        'name',
        'album',
        'track_number',
        'is_active',
        'individual_price',
        'allow_fans_overpay',
    )
    search_fields = ('album', 'lyrics', 'name')
    list_filter = (
        'is_active',
        'allow_fans_overpay',
        'created_at',
        'updated_at',
    )
    ordering = ('track_number', 'name')
    readonly_fields = (
        'formatted_duration',
        'created_at',
        'updated_at',
        'owner',
    )
    list_editable = (
        'individual_price',
        'allow_fans_overpay',
        'is_active',
        'track_number',
    )
    fieldsets = (
        (
            'Основные данные',
            {
                'fields': (
                    'name',
                    'album',
                    'is_active',
                    'track_number',
                    'audio_file',
                    'formatted_duration',
                    'lyrics',
                    'owner',
                    'created_at',
                    'updated_at',
                ),
            },
        ),
        (
            'Цены и оплата',
            {
                'fields': ('individual_price', 'allow_fans_overpay'),
            },
        ),
    )

    @admin.display(description='Длительность')
    def formatted_duration(self, obj):
        """Показывает длительность трека в формате мм:сс."""
        if obj.duration is None:
            return '-'
        minutes = obj.duration // 60
        seconds = obj.duration % 60
        return f'{minutes}:{seconds:02}'
