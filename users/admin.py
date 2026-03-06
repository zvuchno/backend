from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import ArtistLink, ArtistProfile

User = get_user_model()


@admin.register(User)
class CoreUserAdmin(UserAdmin):
    """Админка для кастомной модели пользователя."""


@admin.register(ArtistLink)
class ArtistLinkAdmin(admin.ModelAdmin):
    """Для ссылок и контактов артиста."""


@admin.register(ArtistProfile)
class ArtistProfileAdmin(admin.ModelAdmin):
    """Админка профиля артиста."""
