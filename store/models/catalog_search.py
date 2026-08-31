"""Модель поискового индекса каталога."""

from django.contrib.postgres.search import SearchVectorField
from django.db import models

from store.constants import MAX_CHAR_LENGTH


class CatalogSearch(models.Model):
    """Материализованный поисковый индекс глобального поиска."""

    class EntityType(models.TextChoices):
        ALBUM = 'album', 'Альбом'
        TRACK = 'track', 'Трек'
        MERCH = 'merch', 'Мерч'
        ARTIST = 'artist', 'Артист'

    # Суррогатный id из ROW_NUMBER() в VIEW.
    # Не стабилен между REFRESH MATERIALIZED VIEW — не хранить,
    # не использовать как внешний идентификатор сущности
    # (для этого есть entity_type + entity_id).
    id = models.BigAutoField(
        'ID строки индекса',
        primary_key=True,
    )
    entity_type = models.CharField(
        'Тип сущности',
        max_length=20,
    )
    entity_id = models.PositiveBigIntegerField(
        'ID сущности',
    )
    target_id = models.PositiveBigIntegerField(
        'ID целевой сущности',
        null=True,
    )
    target_slug = models.CharField(
        'Slug цели перехода',
        max_length=MAX_CHAR_LENGTH,
        null=True,
    )
    name = models.CharField(
        'Название',
        max_length=MAX_CHAR_LENGTH,
    )
    kind = models.CharField(
        'Вид карточки',
        max_length=MAX_CHAR_LENGTH,
        null=True,
    )
    artist_name = models.CharField(
        'Артист',
        max_length=MAX_CHAR_LENGTH,
        null=True,
    )
    genre_name = models.CharField(
        'Жанр',
        max_length=MAX_CHAR_LENGTH,
        null=True,
    )
    merch_kind_name = models.CharField(
        'Тип мерча',
        max_length=MAX_CHAR_LENGTH,
        null=True,
    )
    variant_values = models.TextField(
        'Значения вариантов',
        null=True,
    )
    selected_variant_id = models.PositiveBigIntegerField(
        'Выбранный вариант',
        null=True,
    )
    is_publication_ready = models.BooleanField(
        'Готовность к публикации',
        null=True,
    )
    search_text = models.TextField(
        'Поисковый текст',
    )
    search_vector = SearchVectorField(
        'Поисковый вектор',
    )
    image = models.CharField(
        'Изображение',
        max_length=MAX_CHAR_LENGTH,
        null=True,
    )

    class Meta:
        managed = False
        db_table = 'catalog_search'
