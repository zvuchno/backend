"""Модуль админки для модели юридических документов.

Содержит настройку интерфейса Django Admin для модели ConsentDocument.
"""

from django.contrib import admin

from users.models import ConsentDocument


@admin.register(ConsentDocument)
class ConsentDocumentAdmin(admin.ModelAdmin):
    """Админка модели ConsentDocument."""

    list_display = (
        'document_type',
        'version',
        'created_at',
        'updated_at',
        'is_active',
    )
    list_filter = (
        'document_type',
        'is_active',
    )
    readonly_fields = ('created_at', 'content_hash', 'updated_at')
    list_editable = ('is_active',)
    search_fields = ('version', 'content')
    ordering = ('document_type',)
    fieldsets = (
        (
            'Основная информация',
            {
                'fields': ('document_type', 'version', 'is_active'),
            },
        ),
        (
            'Содержимое документа',
            {
                'fields': ('content', 'content_hash'),
            },
        ),
        (
            'Системная информация',
            {
                'fields': ('created_at', 'updated_at'),
            },
        ),
    )
