"""Модуль расширения QuerySet для модели Треков.

Обеспечивает синхронизацию видимости трека
с состоянием его родительского альбома.
"""

from django.db import models


class TrackQuerySet(models.QuerySet):
    """QuerySet для работы с треками.

    Доступность в API вычисляется динамически на основе полей альбома.
    """

    def visible_for(self, user, action):
        # Если админ - отдаем всё
        if user.is_authenticated and user.is_staff:
            return self

        # Базовый фильтр: только активные
        qs = self.filter(is_active=True)

        # Базовая проверка активности альбома
        qs = qs.filter(album__is_active=True)

        allowed_visibilities = ['public']
        # link_only не доступен в list
        if action != 'list':
            allowed_visibilities.append('link_only')

        # Условие: альбом опубликован и имеет подходящий уровень доступа
        album_visibility_q = models.Q(
            album__is_published=True,
            album__visibility__in=allowed_visibilities,
        )
        # Владелец альбома видит свои треки, даже если альбом скрыт
        if user.is_authenticated:
            return qs.filter(album_visibility_q | models.Q(album__owner=user))
        return qs.filter(album_visibility_q)
