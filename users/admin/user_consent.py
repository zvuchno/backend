"""Модуль админки для модели юридических согласий.

Содержит настройку интерфейса Django Admin для модели ConsentDocument.
"""

from django.contrib import admin

from users.models import UserConsent


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    """Админка модели UserConsent."""

    list_display = (
        'user__email',
        'document',
        'accepted_at',
    )
    list_filter = ('user__email',)
    search_fields = ('user__email',)
