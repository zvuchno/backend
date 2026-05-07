"""Модуль админки для модели типов юридических документов.

Содержит настройку интерфейса Django Admin для модели DocumentType.
"""

from django.contrib import admin

from users.models import DocumentType


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    """Админка модели DocumentType."""

    list_display = ('name',)
    list_filter = ('name',)
    search_fields = ('name',)
    ordering = ('name',)
