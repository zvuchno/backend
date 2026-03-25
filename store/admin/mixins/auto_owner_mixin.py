"""Миксин админки Django: AutoOwnerAdminMixin.

Миксин для автоматического назначения владельца (owner) объектов
при сохранении в админке.
"""

from django.contrib.auth import get_user_model

User = get_user_model()


class AutoOwnerAdminMixin:
    """Mixin. Автоматически назначает владельца.

    Для моделей в админке, где нужно автоматически
    проставлять owner при сохранении через интерфейс.
    """

    def save_model(self, request, obj, form, change):
        """Назначает владельца (owner) при сохранении модели через админку."""
        if hasattr(obj, 'owner_id') and not obj.owner_id:
            obj.owner = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """Сохраняет inline-объекты с автоматическим назначением владельца."""
        # Получаем объекты из formset, но не сохраняем сразу
        instances = formset.save(commit=False)

        # Удаляем объекты, отмеченные на удаление
        for obj in formset.deleted_objects:
            obj.delete()

        for obj in instances:
            # Если поле owner есть и оно пустое — назначаем пользователя
            if hasattr(obj, 'owner_id') and not getattr(obj, 'owner_id', None):
                obj.owner = request.user

            obj.save()

        formset.save_m2m()
