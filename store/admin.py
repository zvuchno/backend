from django.contrib import admin

from .models import Album, Genre, Track


class AutoUserAdminMixin:

    def save_model(self, request, obj, form, change):
        # Если объект ещё не имеет user, ставим текущего
        if not getattr(obj, 'user_id', None):
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(Album)
class AlbumAdmin(AutoUserAdminMixin, admin.ModelAdmin):

    list_display = (
        'name',
        'release_date',
        'genre',
        'price',
        'allow_fans_to_pay_more',
        'visibility',
    )
    search_fields = ('genre', 'name',)
    list_filter = ('genre', 'visibility',)
    ordering = ('name',)
    readonly_fields = ('created_at', 'user',)
    list_editable = (
        'price',
        'allow_fans_to_pay_more',
        'visibility',
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
                'user',
                'created_at',
            )
        }),
        ('Цены и оплата', {
            'fields': ('price', 'allow_fans_to_pay_more',)
        }),
    )


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = (
        'name',
    )
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Track)
class TrackAdmin(AutoUserAdminMixin, admin.ModelAdmin):
    list_display = (
        'name',
        'album',
        'individual_price',
        'allow_fans_to_pay_more',
    )
    search_fields = ('album', 'lyrics', 'name',)
    list_filter = ('album', 'allow_fans_to_pay_more',)
    ordering = ('name',)
    readonly_fields = ('created_at', 'user',)
    list_editable = (
        'individual_price',
        'allow_fans_to_pay_more',
    )
    fieldsets = (
        ('Основные данные', {
            'fields': (
                'name',
                'album',
                'audio_file',
                'lyrics',
                'user',
                'created_at',
            )
        }),
        ('Цены и оплата', {
            'fields': ('individual_price', 'allow_fans_to_pay_more',)
        }),
    )
