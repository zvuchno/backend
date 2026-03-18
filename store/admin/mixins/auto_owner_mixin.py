"""Миксин админки Django: AutoOwnerAdminMixin.

Миксин для автоматического назначения владельца (owner) объектов
при сохранении в админке.
"""


class AutoOwnerAdminMixin:
    """Mixin: автоматически назначает владельца при сохранении объектов."""

    def save_model(self, request, obj, form, change):
        """Назначает пользователя владельцем при сохранении через админку."""
        if not getattr(obj, 'owner_id', None):
            obj.owner = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """Назначает текущего пользователя владельцем.

        Для всех объектов из Inline при сохранении формы.
        """
        instances = formset.save(commit=False)
        for obj in instances:
            if not getattr(obj, 'owner_id', None):
                obj.owner = request.user
            obj.save()
        formset.save_m2m()
