"""Модель размещения музыкальной записи в релизе."""

from django.db import models

from common.models.abstract import ActivatableModel, TimestampModel

from store.constants import MAX_STR_LENGTH
from store.querysets.track_visibility import TrackQuerySet


class ReleaseTrack(ActivatableModel, TimestampModel):
    """Связь музыкального трека с релизом."""

    release = models.ForeignKey(
        'store.Album',
        on_delete=models.CASCADE,
        related_name='tracks',
        verbose_name='Релиз',
    )
    recording = models.ForeignKey(
        'store.Recording',
        on_delete=models.PROTECT,
        related_name='release_tracks',
        verbose_name='Запись',
    )
    position = models.PositiveIntegerField(
        'Порядок',
        null=True,
        blank=True,
    )

    @property
    def name(self):
        return self.recording.name

    @property
    def artist(self):
        return self.release.artist

    @property
    def payout_recipient(self):
        return self.release.payout_recipient

    objects = TrackQuerySet.as_manager()

    def __str__(self):
        if self.position is not None:
            return f'{self.position}. {self.name[:MAX_STR_LENGTH]}'
        return self.name[:MAX_STR_LENGTH]

    class Meta:
        verbose_name = 'трек релиза'
        verbose_name_plural = 'треки релиза'
        ordering = ('release', 'position', 'id')
        constraints = [
            models.UniqueConstraint(
                fields=('release', 'recording'),
                name='unique_release_recording',
            ),
        ]
