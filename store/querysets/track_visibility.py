"""Модуль расширения QuerySet для модели Треков.

Обеспечивает синхронизацию видимости трека
с состоянием его родительского релиза.
"""

from django.db import models

from common.access import managed_artist_q


class TrackQuerySet(models.QuerySet):
    """QuerySet для работы с треками.

    Доступность в API вычисляется динамически на основе полей релиза.
    """

    def visible_for(self, user, action):
        # Если админ - отдаем всё
        if user.is_authenticated and user.is_staff:
            return self

        # Базовый фильтр: только активные
        qs = self.filter(is_active=True)

        # Базовая проверка активности релиза
        qs = self.filter(
            is_active=True,
            recording__is_active=True,
            release__is_active=True,
        )

        allowed_visibilities = ['public']
        # link_only не доступен в list
        if action != 'list':
            allowed_visibilities.append('link_only')

        # Условие: релиз опубликован и имеет подходящий уровень доступа
        release_visibility_q = models.Q(
            release__is_published=True,
            release__visibility__in=allowed_visibilities,
        )
        # Владелец релиза видит свои треки, даже если релиз скрыт
        if user.is_authenticated:
            return qs.filter(
                release_visibility_q
                | managed_artist_q(user, prefix='release__artist'),
            )
        return qs.filter(release_visibility_q)

    def playable(self):
        """Возвращает треки, которые разрешено воспроизводить."""
        return self.filter(
            is_active=True,
            recording__is_active=True,
            release__is_active=True,
        )

    def for_player(self, user, *, preview: bool = False):
        """Треки для плеера, включая черновики при предпросмотре."""
        regular = (
            self
            .playable()
            .visible_for(user, action='retrieve')
            .filter(release__is_published=True)
        )

        if not preview:
            return regular

        preview_public = self.playable().filter(
            release__artist__is_active=True,
            release__visibility='public',
        )
        return regular | preview_public
