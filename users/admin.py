from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import ArtistContact, ArtistSocial, ArtistProfile

User = get_user_model()


@admin.register(User)
class CoreUserAdmin(UserAdmin):
    """Админка для кастомной модели пользователя."""


@admin.register(ArtistContact)
class ArtistContactAdmin(admin.ModelAdmin):
    """Для контактов артиста."""


@admin.register(ArtistSocial)
class ArtistSocialAdmin(admin.ModelAdmin):
    """Для ссылок на соцсети артиста."""


@admin.register(ArtistProfile)
class ArtistProfileAdmin(admin.ModelAdmin):
    """Админка профиля артиста."""
