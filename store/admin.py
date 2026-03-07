from django.contrib import admin

from .models import Genre, Album


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):

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
    list_filter = ('genre',)
    readonly_fields = ('created_at',)
    list_editable = (
        'price',
        'allow_fans_to_pay_more',
    )
    fieldsets = (
        ('Основные данные', {
            'fields': (
                'name',
                'genre',
                'release_date',
                'description',
                'cover_image',
                'visibility',
                'created_at',
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


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = (
        'name',
    )
    search_fields = ('name',)
    list_filter = ('name',)
