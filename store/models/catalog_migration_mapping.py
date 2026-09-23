"""Реестр соответствий разовой миграции каталога."""

from django.db import models


class CatalogMigrationMapping(models.Model):
    """Связывает entity_id замороженного bundle с Django PK."""

    class EntityType(models.TextChoices):
        """Поддерживаемые типы сущностей bundle."""

        PROFILE = 'profile', 'Профиль'
        RELEASE = 'release', 'Релиз'
        TRACK = 'track', 'Трек'
        MERCH = 'merch', 'Мерч'
        PRODUCT = 'product', 'Продукт'
        VARIANT = 'variant', 'Вариант'

    bundle_version = models.CharField(max_length=32)
    entity_type = models.CharField(
        max_length=16,
        choices=EntityType.choices,
    )
    source_entity_id = models.CharField(max_length=255)
    django_pk = models.PositiveBigIntegerField()

    class Meta:
        verbose_name = 'соответствие миграции каталога'
        verbose_name_plural = 'соответствия миграции каталога'
        constraints = (
            models.UniqueConstraint(
                fields=(
                    'bundle_version',
                    'entity_type',
                    'source_entity_id',
                ),
                name='unique_catalog_migration_source',
            ),
            models.UniqueConstraint(
                fields=('entity_type', 'django_pk'),
                name='unique_catalog_migration_target',
            ),
        )

    def __str__(self):
        return (
            f'{self.bundle_version}:{self.entity_type}:'
            f'{self.source_entity_id} -> {self.django_pk}'
        )
