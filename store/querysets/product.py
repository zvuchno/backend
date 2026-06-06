from django.db import models
from django.db.models import OuterRef, Prefetch, Subquery
from django.db.models.functions import ExtractYear


class ProductQuerySet(models.QuerySet):
    """QuerySet товаров.

    TODO Убрать лишнее, использовать фабрику.
    """

    CATALOG_TYPE_ALL = 'all'
    CATALOG_TYPE_ALBUM = 'album'
    CATALOG_TYPE_MERCH = 'merch'

    def published_tracks(self):
        """Возвращает опубликованные треки для карточек.

        Треки видимы через родительский альбом.
        """
        return self.filter(
            track__isnull=False,
            track__is_active=True,
            track__album__is_active=True,
            track__album__is_published=True,
            track__album__visibility='public',
        )

    def published_albums(self):
        """Возвращает опубликованные альбомы каталога."""
        return self.filter(
            album__isnull=False,
            album__is_active=True,
            album__is_published=True,
            album__visibility='public',
        )

    def published_merch(self):
        """Возвращает опубликованный мерч каталога."""
        return self.filter(
            merch__isnull=False,
            merch__is_active=True,
            merch__is_published=True,
            merch__visibility='public',
        )

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
                album__visibility='public',
            )
            | models.Q(
                merch__isnull=False,
                merch__is_active=True,
                merch__is_published=True,
                merch__visibility='public',
            ),
        )

    def with_selected_variant_id(self):
        """Добавляет ID варианта для предвыбора в детальной карточке."""
        from store.models.product_variant import ProductVariant

        active_variant_id = (
            ProductVariant.objects
            .filter(
                product_id=OuterRef('pk'),
                is_active=True,
            )
            .order_by('id')
            .values('id')[:1]
        )

        return self.annotate(
            selected_variant_id=models.Case(
                models.When(
                    product_type='album',
                    then=Subquery(active_variant_id),
                ),
                models.When(
                    product_type='merch',
                    merch__kind__is_carrier=True,
                    merch__album_id__isnull=False,
                    then=Subquery(active_variant_id),
                ),
                default=models.Value(None),
                output_field=models.IntegerField(),
            ),
        )

    def with_album_card_data(self):
        """Подтягивает данные для карточек альбомов."""
        return self.select_related('album')

    def with_track_card_data(self):
        """Подтягивает данные для карточек треков."""
        return self.select_related(
            'track',
            'track__album',
        )

    def with_merch_card_data(self):
        """Подтягивает данные для карточек мерча и носителей."""
        return self.select_related(
            'merch',
        ).prefetch_related(
            Prefetch(
                'merch__images_merch',
                to_attr='prefetched_images',
            ),
        )

    def with_album_card_annotations(self):
        """Добавляет вычисляемые поля карточек альбомов."""
        return self.annotate(
            artist_name=models.F('album__owner__artist_profile__name'),
            kind=models.Case(
                models.When(
                    album__is_single=True,
                    then=models.Value('Сингл'),
                ),
                default=models.Value('Альбом'),
                output_field=models.CharField(),
            ),
            year=ExtractYear('album__release_date'),
            target_type=models.Value(
                'release',
                output_field=models.CharField(),
            ),
            target_id=models.F('album_id'),
            catalog_created_at=models.F('album__created_at'),
        )

    def with_merch_card_annotations(self):
        """Добавляет вычисляемые поля карточек мерча и носителей."""
        return self.annotate(
            artist_name=models.F('merch__owner__artist_profile__name'),
            kind=models.F('merch__kind__name'),
            year=models.Value(
                None,
                output_field=models.IntegerField(),
            ),
            target_type=models.Case(
                models.When(
                    merch__kind__is_carrier=True,
                    merch__album_id__isnull=False,
                    then=models.Value('release'),
                ),
                default=models.Value('merch'),
                output_field=models.CharField(),
            ),
            target_id=models.Case(
                models.When(
                    merch__kind__is_carrier=True,
                    merch__album_id__isnull=False,
                    then=models.F('merch__album_id'),
                ),
                default=models.F('merch_id'),
                output_field=models.IntegerField(),
            ),
            catalog_created_at=models.F('merch__created_at'),
        )

    def with_track_card_annotations(self):
        """Добавляет вычисляемые поля карточек треков."""
        return self.annotate(
            artist_name=models.F(
                'track__album__owner__artist_profile__name',
            ),
            kind=models.Value(
                'Трек',
                output_field=models.CharField(),
            ),
            year=ExtractYear('track__album__release_date'),
            target_type=models.Value(
                'track',
                output_field=models.CharField(),
            ),
            target_id=models.F('track_id'),
            catalog_created_at=models.F('track__created_at'),
        )

    def with_catalog_card_annotations(self):
        """Добавляет вычисляемые поля карточек основного каталога.

        Используется для смешанной выдачи альбомов и мерча.
        """
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
                output_field=models.CharField(),
            ),
            year=models.Case(
                models.When(
                    product_type='album',
                    then=ExtractYear('album__release_date'),
                ),
                default=models.Value(None),
                output_field=models.IntegerField(),
            ),
            target_type=models.Case(
                models.When(
                    product_type='album',
                    then=models.Value('release'),
                ),
                models.When(
                    product_type='merch',
                    merch__kind__is_carrier=True,
                    merch__album_id__isnull=False,
                    then=models.Value('release'),
                ),
                default=models.F('product_type'),
                output_field=models.CharField(),
            ),
            target_id=models.Case(
                models.When(
                    product_type='merch',
                    merch__kind__is_carrier=True,
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
                output_field=models.DateTimeField(),
            ),
        )

    def for_album_cards(self):
        """Готовит queryset для карточек альбомов."""
        return (
            self
            .published_albums()
            .with_album_card_data()
            .with_album_card_annotations()
            .with_selected_variant_id()
        )

    def for_merch_cards(self):
        """Готовит queryset для карточек мерча."""
        return (
            self
            .published_merch()
            .with_merch_card_data()
            .with_merch_card_annotations()
            .with_selected_variant_id()
        )

    def for_track_cards(self):
        """Готовит queryset для карточек треков."""
        return (
            self
            .published_tracks()
            .with_track_card_data()
            .with_track_card_annotations()
        )

    def for_catalog_cards(self):
        """Готовит queryset для карточек основного каталога.

        Основной каталог сейчас содержит альбомы и мерч.
        Треки в него не входят.
        """
        return (
            self
            .published_catalog_content()
            .with_album_card_data()
            .with_merch_card_data()
            .with_catalog_card_annotations()
            .with_selected_variant_id()
        )

    def for_catalog_type(self, catalog_type):
        """Готовит queryset каталога под выбранный тип витрины."""
        if catalog_type == self.CATALOG_TYPE_ALBUM:
            return self.for_album_cards()

        if catalog_type == self.CATALOG_TYPE_MERCH:
            return self.for_merch_cards()

        return self.for_catalog_cards()
