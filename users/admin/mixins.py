"""Миксины для админки."""

from django.contrib import admin
from django.utils.html import format_html


class ImagePreviewMixin:
    """Mixin для отображения превью изображения в админке."""

    @admin.display(description='Обложка')
    def image_preview(self, obj):
        """Отдает превью изображения в html"""
        if obj and obj.cover:
            return format_html(  # noqa
                '<a href="{url}" target="_blank">'
                '<img src="{url}" style="height:80px;border-radius:4px;" '
                'loading="lazy"></a>',
                url=obj.cover.url
            )
        return '—'
