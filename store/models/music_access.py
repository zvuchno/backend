from django.conf import settings
from django.db import models


class ListenerTrackAccess(models.Model):
    """Read-only модель доступа слушателя к купленному треку."""

    pk = models.CompositePrimaryKey('user', 'track')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING,
        related_name='+',  # Отключение обратной связи.
        verbose_name='Пользователь',
    )
    track = models.ForeignKey(
        'store.Track',
        on_delete=models.DO_NOTHING,
        related_name='+',  # Отключение обратной связи.
        verbose_name='Трек',
    )

    class Meta:
        managed = False  # ORM не управляет моделью.
        db_table = 'listener_track_access'
        verbose_name = 'доступ к треку'
        verbose_name_plural = 'доступы к трекам'

    def __str__(self):
        return f'{self.user_id} - {self.track_id}'


class ListenerAlbumAccess(models.Model):
    """Read-only модель доступа слушателя к релизу."""

    pk = models.CompositePrimaryKey('user', 'album')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING,
        related_name='+',
        verbose_name='Пользователь',
    )
    album = models.ForeignKey(
        'store.Album',
        on_delete=models.DO_NOTHING,
        related_name='+',
        verbose_name='Альбом',
    )
    is_fully_available = models.BooleanField(
        'Релиз доступен полностью',
    )

    class Meta:
        managed = False
        db_table = 'listener_album_access'
        verbose_name = 'доступ к релизу'
        verbose_name_plural = 'доступы к релизам'

    def __str__(self):
        return f'{self.user_id} - {self.album_id}'
