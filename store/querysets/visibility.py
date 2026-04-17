"""Расширения QuerySet для работы с доступом и выборкой данных."""

from django.db import models


class VisibilityQuerySet(models.QuerySet):
    """QuerySet с правилами доступа и видимости объектов.

    Фильтрует объекты по:
    - активности
    - статусу публикации
    - уровню видимости
    - правам пользователя
    """

    def visible_for(self, user, action):
        # Если админ - отдаем всё
        if user.is_authenticated and user.is_staff:
            return self

        # Базовый фильтр: только активные
        qs = self.filter(is_active=True)

        allowed_visibilities = ['public']
        # link_only не доступен в list
        if action != 'list':
            allowed_visibilities.append('link_only')

        # Базовое условие доступа
        base_q = models.Q(
            is_published=True,
            visibility__in=allowed_visibilities,
        )
        # Владелец + публичное
        if user.is_authenticated:
            return qs.filter(base_q | models.Q(owner=user))
        return qs.filter(base_q)
