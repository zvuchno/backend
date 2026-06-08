"""Модуль расширения QuerySet для модели заказа."""

from django.db import models

from store.querysets.variant_annotations import build_target_annotations


class OrderQuerySet(models.QuerySet):
    """Кверисет для работы с заказами ."""

    def with_target_annotations(self):
        """Добавляет данные для перехода на целевую карточку."""
        return self.annotate(
            **build_target_annotations('product_variant__product'),
        )
