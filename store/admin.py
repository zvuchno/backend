from django.contrib import admin

from .models import Album, Single


class ReleaseAdminMixin:
    """Общие настройки для админки релизов."""

    list_display = (
        'name',
        'release_date',
        'genre',
        'price',
        'allow_fans_to_pay_more',
        'description',
    )
    search_fields = ('name',)
    ordering = ('name',)
    list_filter = ('name', 'genre',)
    list_editable = (
        'price',
        'allow_fans_to_pay_more',
    )
    fieldsets = (
        ('Основные данные', {
            'fields': ('name', 'release_date', 'genre', 'description',)
        }),
        ('Цены и оплата', {
            'fields': ('price', 'allow_fans_to_pay_more'),
        }),
    )

    def save_model(self, request, obj, form, change):
        # Если объект не имеет пользователя, ставим текущего
        if not obj.user_id:
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(Album)
class AlbumAdmin(ReleaseAdminMixin, admin.ModelAdmin):
    pass


@admin.register(Single)
class SingleAdmin(ReleaseAdminMixin, admin.ModelAdmin):
    pass
