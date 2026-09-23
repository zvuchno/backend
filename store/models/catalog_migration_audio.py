"""Состояние подключения аудио разовой миграции каталога."""

from django.db import models

from common.models.abstract import TimestampModel


class CatalogMigrationAudioState(TimestampModel):
    """Хранит возобновляемое состояние аудио одного TRACK mapping."""

    class Status(models.TextChoices):
        """Состояния, которые не выдают очередь за готовое аудио."""

        PREPARED = 'prepared', 'Подготовлено'
        COPYING = 'copying', 'Копируется в staging'
        STAGED = 'staged', 'Оригинал подключён'
        QUEUED = 'queued', 'Поставлено в очередь'
        PROCESSING = 'processing', 'Обрабатывается'
        READY = 'ready', 'Готово'
        FAILED = 'failed', 'Ошибка'

    mapping = models.OneToOneField(
        'store.CatalogMigrationMapping',
        on_delete=models.PROTECT,
        related_name='audio_state',
    )
    track = models.OneToOneField(
        'store.Track',
        on_delete=models.PROTECT,
        related_name='migration_audio_state',
    )
    upload = models.OneToOneField(
        'store.TrackUpload',
        on_delete=models.PROTECT,
        related_name='migration_audio_state',
        null=True,
        blank=True,
    )
    asset_id = models.CharField(max_length=255)
    source_key = models.CharField(max_length=1000)
    source_sha256 = models.CharField(max_length=64)
    expected_size = models.PositiveBigIntegerField()
    staging_key = models.CharField(max_length=500, unique=True)
    original_key = models.CharField(max_length=500, unique=True)
    preview_key = models.CharField(max_length=500, blank=True)
    stream_key = models.CharField(max_length=500, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PREPARED,
    )
    error = models.TextField(blank=True)
    queued_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'состояние аудио миграции каталога'
        verbose_name_plural = 'состояния аудио миграции каталога'

    def __str__(self):
        return f'{self.mapping}: {self.status}'
