"""Миксин админки Django: CommerceInitializationMixin."""

from store.services import ProductService


class CommerceMixin:
    """Миксин для ModelAdmin, обеспечивающий целостность коммерческих данных.

    Гарантирует наличие связанных объектов Product
    и Variant через ProductService.
    """

    def save_related(self, request, form, formsets, change):
        """Обеспечивает создание коммерческой инфраструктуры после сохранения.

        Вызывает сервис, который создаёт Product + Variant только если их нет.
        """
        super().save_related(request, form, formsets, change)

        ProductService.ensure_commerce(form.instance)
