"""Миксин админки Django: AutoOwnerAdminMixin.

Миксин для автоматического назначения владельца (owner) объектов
при сохранении в админке.
"""

from users.models import ArtistProfile


class AutoOwnerAdminMixin:
    """Mixin: автоматически назначает владельца при сохранении объектов."""

    def get_artist_profile(self, user):
        """Возвращает профиль артиста пользователя, создаёт если нет."""
        artist_profile, created = ArtistProfile.objects.get_or_create(
            owner=user,
        )
        return artist_profile

    def save_model(self, request, obj, form, change):
        """Назначает артиста владельцем при сохранении через админку."""
        if not getattr(obj, 'owner_id', None):
            obj.owner = self.get_artist_profile(request.user)
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """Назначает текущего артиста владельцем.

        Для всех объектов из Inline при сохранении формы.
        """
        instances = formset.save(commit=False)
        for obj in instances:
            if not getattr(obj, 'owner_id', None):
                obj.owner = self.get_artist_profile(request.user)
            obj.save()
        formset.save_m2m()
