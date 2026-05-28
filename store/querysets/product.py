from django.db import models
from django.db.models.functions import ExtractYear


class ProductQuerySet(models.QuerySet):
    """QuerySet товаров."""

    def published_catalog_content(self):
        """Возвращает опубликованные товары основного каталога.

        В основной каталог сейчас входят альбомы и мерч.
        Треки не добавляются, потому что они видимы через альбом.
        """
        return self.filter(
            models.Q(
                album__isnull=False,
                album__is_active=True,
                album__is_published=True,
            )
            | models.Q(
                merch__isnull=False,
                merch__is_active=True,
                merch__is_published=True,
            ),
        )

    def published_card_content(self):
        """Возвращает опубликованный контент для универсальных карточек.

        Использовать в ручках, где могут быть не только товары основного
        каталога, но и треки: избранное, заказы, кабинет слушателя.
        """
        return self.filter(
            models.Q(
                album__isnull=False,
                album__is_active=True,
                album__is_published=True,
            )
            | models.Q(
                merch__isnull=False,
                merch__is_active=True,
                merch__is_published=True,
            )
            | models.Q(
                track__isnull=False,
                track__is_active=True,
                track__album__is_active=True,
                track__album__is_published=True,
            ),
        )

    def with_album_card_data(self):
        """Подтягивает данные для карточек альбомов."""
        return self.select_related(
            'album',
            'album__owner',
            'album__owner__artist_profile',
        )

    def with_track_card_data(self):
        """Подтягивает данные для карточек треков."""
        return self.select_related(
            'track',
            'track__album',
            'track__owner',
            'track__owner__artist_profile',
        )

    def with_merch_card_data(self):
        """Подтягивает данные для карточек мерча и носителей."""
        return self.select_related(
            'merch',
            'merch__owner',
            'merch__owner__artist_profile',
            'merch__kind',
            'merch__album',
        ).prefetch_related(
            'merch__images_merch',
        )

    def with_card_annotations(self):
        """Добавляет вычисляемые поля единой карточки товара."""
        return self.annotate(
            artist_name=models.Case(
                models.When(
                    product_type='album',
                    then=models.F('album__owner__artist_profile__name'),
                ),
                models.When(
                    product_type='merch',
                    then=models.F('merch__owner__artist_profile__name'),
                ),
                models.When(
                    product_type='track',
                    then=models.F(
                        'track__owner__artist_profile__name',
                    ),
                ),
                output_field=models.CharField(),
            ),
            kind=models.Case(
                models.When(
                    product_type='album',
                    album__is_single=True,
                    then=models.Value('Сингл'),
                ),
                models.When(
                    product_type='album',
                    album__is_single=False,
                    then=models.Value('Альбом'),
                ),
                models.When(
                    product_type='merch',
                    then=models.F('merch__kind__name'),
                ),
                models.When(
                    product_type='track',
                    then=models.Value('Трек'),
                ),
                output_field=models.CharField(),
            ),
            year=models.Case(
                models.When(
                    product_type='album',
                    then=ExtractYear('album__release_date'),
                ),
                models.When(
                    product_type='track',
                    then=ExtractYear('track__album__release_date'),
                ),
                default=models.Value(None),
                output_field=models.IntegerField(),
            ),
            target_type=models.Case(
                models.When(
                    product_type='merch',
                    merch__is_carrier=True,
                    merch__album_id__isnull=False,
                    then=models.Value('album'),
                ),
                default=models.F('product_type'),
                output_field=models.CharField(),
            ),
            target_id=models.Case(
                models.When(
                    product_type='merch',
                    merch__is_carrier=True,
                    merch__album_id__isnull=False,
                    then=models.F('merch__album_id'),
                ),
                models.When(
                    product_type='album',
                    then=models.F('album_id'),
                ),
                models.When(
                    product_type='merch',
                    then=models.F('merch_id'),
                ),
                models.When(
                    product_type='track',
                    then=models.F('track_id'),
                ),
                output_field=models.IntegerField(),
            ),
            catalog_created_at=models.Case(
                models.When(
                    product_type='album',
                    then=models.F('album__created_at'),
                ),
                models.When(
                    product_type='merch',
                    then=models.F('merch__created_at'),
                ),
                models.When(
                    product_type='track',
                    then=models.F('track__created_at'),
                ),
                output_field=models.DateTimeField(),
            ),
        )

    def for_catalog_cards(self):
        """Готовит queryset для CatalogCardSerializer в основном каталоге.

        Основной каталог сейчас содержит альбомы и мерч.
        Треки в него не входят.
        """
        return (
            self
            .published_catalog_content()
            .with_album_card_data()
            .with_merch_card_data()
            .with_card_annotations()
        )

    def for_all_card_types(self):
        """Готовит queryset для карточек всех типов товаров.

        Использовать в ручках, где могут встретиться треки:
        избранное, заказы, кабинет слушателя.
        """
        return (
            self
            .published_card_content()
            .with_album_card_data()
            .with_merch_card_data()
            .with_track_card_data()
            .with_card_annotations()
        )

    def for_track_cards(self):
        """Готовит queryset для карточек треков."""
        return (
            self
            .published_card_content()
            .with_track_card_data()
            .with_card_annotations()
        )
