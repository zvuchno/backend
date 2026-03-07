from django.contrib import admin

from .models import Release


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'release_type',
        'release_date',
        'genre',
        'price',
        'allow_fans_to_pay_more',
        'description',
    )
    search_fields = ('name',)
    ordering = ('name',)
    list_filter = ('release_type', 'genre',)
    list_editable = (
        'price',
        'allow_fans_to_pay_more',
    )
    fieldsets = (
        ('Основные данные', {
            'fields': (
                'name',
                'release_type',
                'release_date',
                'genre',
                'description',
                'visibility',
                'cover_image',
            )
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
