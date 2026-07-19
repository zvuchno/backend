"""Миксин админки Django: AutoCreatedByAdminMixin.

Миксин для автоматического назначения создателя (created_by) объектов
при сохранении в админке.
"""


class AutoCreatedByAdminMixin:
    """Mixin. Автоматически назначает создателя.

    Для моделей в админке, где нужно автоматически
    проставлять created_by при сохранении через интерфейс.
    """

    def save_model(self, request, obj, form, change):
        """Назначает создателя при сохранении модели через админку."""
        if hasattr(obj, 'created_by_id') and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """Сохраняет inline-объекты с автоматическим назначением создателя."""
        # Получаем объекты из formset, но не сохраняем сразу
        instances = formset.save(commit=False)

        # Удаляем объекты, отмеченные на удаление
        for obj in formset.deleted_objects:
            obj.delete()

        for obj in instances:
            # Если поле created_by есть и оно пустое — назначаем пользователя
            if hasattr(obj, 'created_by_id') and not getattr(
                obj,
                'created_by_id',
                None,
            ):
                obj.created_by = request.user

            obj.save()

        formset.save_m2m()
