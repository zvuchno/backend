"""Сценарии создания тестовых данных магазина."""

from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from store.models import Album, Merch
from store.tests.factories import (
    AlbumFactory,
    AlbumProductFactory,
    GenreFactory,
    MerchFactory,
    MerchImageFactory,
    MerchKindFactory,
    MerchProductFactory,
    ProductVariantFactory,
)
from users.tests.factories import ArtistProfileFactory


def create_album_product(
    *,
    artist=None,
    payout_recipient=None,
    created_by=None,
    artist_name=None,
    genre=None,
    name='Тестовый альбом',
    price=Decimal('1000.00'),
    allow_overpay=False,
    is_published=True,
    visibility='public',
    with_variant=True,
):
    """Создает опубликованный альбом, товар и цифровой вариант."""
    artist = artist or ArtistProfileFactory()

    if artist_name:
        artist.name = artist_name
        artist.save(update_fields=('name', 'slug'))

    album = AlbumFactory(
        artist=artist,
        payout_recipient=(payout_recipient or artist.default_payout_recipient),
        created_by=(
            created_by or artist.user or artist.default_payout_recipient
        ),
        genre=genre or GenreFactory(),
        name=name,
        is_published=is_published,
        visibility=visibility,
    )
    product = AlbumProductFactory(
        album=album,
        price=price,
        allow_overpay=allow_overpay,
        property_name='Формат',
    )

    if with_variant:
        ProductVariantFactory(
            product=product,
            property_value='digital',
            stock=1,
        )

    return product


def create_merch_product(
    *,
    artist=None,
    payout_recipient=None,
    created_by=None,
    artist_name=None,
    kind=None,
    name='Тестовый мерч',
    price=Decimal('1500.00'),
    allow_overpay=False,
    is_published=True,
    visibility='public',
    album=None,
    with_variant=True,
    with_image=False,
):
    """Создает мерч, товар и вариант."""
    artist = artist or ArtistProfileFactory()

    if artist_name:
        artist.name = artist_name
        artist.save(update_fields=('name', 'slug'))

    merch = MerchFactory(
        artist=artist,
        payout_recipient=(payout_recipient or artist.default_payout_recipient),
        created_by=(
            created_by or artist.user or artist.default_payout_recipient
        ),
        kind=kind or MerchKindFactory(is_carrier=False),
        album=album,
        name=name,
        is_published=is_published,
        visibility=visibility,
    )
    product = MerchProductFactory(
        merch=merch,
        price=price,
        allow_overpay=allow_overpay,
        property_name='Размер',
    )

    if with_variant:
        ProductVariantFactory(
            product=product,
            property_value='M',
            stock=10,
        )

    if with_image:
        MerchImageFactory(
            merch=merch,
            is_main=True,
        )

    return product


def create_carrier_product(
    *,
    artist=None,
    payout_recipient=None,
    created_by=None,
    artist_name=None,
    album=None,
    genre=None,
    kind=None,
    name='Тестовый винил',
    price=Decimal('2500.00'),
    with_variant=True,
):
    """Создает физический носитель, связанный с альбомом."""
    if album is not None:
        if artist is not None and artist.pk != album.artist_id:
            raise ValueError(
                'Артист носителя должен совпадать с артистом альбома.',
            )

        if (
            payout_recipient is not None
            and payout_recipient.pk != album.payout_recipient_id
        ):
            raise ValueError(
                'Получатель выплат носителя должен совпадать '
                'с получателем выплат альбома.',
            )

        artist = artist or album.artist
        payout_recipient = payout_recipient or album.payout_recipient
        created_by = created_by or album.created_by

    artist = artist or ArtistProfileFactory()

    if album is None:
        album = AlbumFactory(
            artist=artist,
            payout_recipient=(
                payout_recipient or artist.default_payout_recipient
            ),
            created_by=(
                created_by or artist.user or artist.default_payout_recipient
            ),
            genre=genre or GenreFactory(),
            name='Альбом для носителя',
            is_published=True,
            visibility='public',
        )

    carrier_kind = kind or MerchKindFactory(
        name='Винил',
        slug='vinyl',
        is_carrier=True,
    )

    return create_merch_product(
        artist=artist,
        payout_recipient=(payout_recipient or album.payout_recipient),
        created_by=created_by or album.created_by,
        artist_name=artist_name,
        kind=carrier_kind,
        name=name,
        price=price,
        album=album,
        with_variant=with_variant,
    )


def create_catalog_type_dataset():
    """Создает набор товаров разных типов для проверки type-фильтра."""
    album = create_album_product(name='Цифровой альбом')
    merch = create_merch_product(name='Футболка')
    carrier = create_carrier_product(name='Винил')

    return {
        'album': album,
        'merch': merch,
        'carrier': carrier,
    }


def create_catalog_date_sorting_dataset():
    """Создает набор товаров для проверки сортировки по дате контента."""
    old_product = create_album_product(name='Old Album')
    middle_product = create_merch_product(name='Middle Merch')
    new_product = create_album_product(name='New Album')

    set_content_created_at(old_product, aware_datetime(2026, 1, 1))
    set_content_created_at(middle_product, aware_datetime(2026, 2, 1))
    set_content_created_at(new_product, aware_datetime(2026, 3, 1))

    return {
        'old': old_product,
        'middle': middle_product,
        'new': new_product,
    }


def set_content_created_at(product, value):
    """Задает created_at связанного контента товара."""
    if product.album_id:
        Album.objects.filter(pk=product.album_id).update(created_at=value)
        product.album.refresh_from_db(fields=('created_at',))
        return product.album

    if product.merch_id:
        Merch.objects.filter(pk=product.merch_id).update(created_at=value)
        product.merch.refresh_from_db(fields=('created_at',))
        return product.merch

    raise AssertionError('У товара нет связанного album или merch.')


def create_catalog_visibility_dataset():
    """Создает видимые и невидимые товары для проверки публичности каталога."""
    public_album = create_album_product(
        name='Public Album',
        is_published=True,
        visibility='public',
    )
    unpublished_album = create_album_product(
        name='Unpublished Album',
        is_published=False,
        visibility='public',
    )
    hidden_album = create_album_product(
        name='Hidden Album',
        is_published=True,
        visibility='hidden',
    )
    link_only = create_album_product(
        name='Link Only Album',
        is_published=True,
        visibility='link_only',
    )
    public_merch = create_merch_product(
        name='Public Merch',
        is_published=True,
        visibility='public',
    )

    return {
        'public_album': public_album,
        'unpublished_album': unpublished_album,
        'hidden_album': hidden_album,
        'link_only': link_only,
        'public_merch': public_merch,
    }


def get_product_ids(response):
    """Возвращает id товаров из paginated-ответа каталога."""
    return [item['product_id'] for item in response.data['results']]


def get_response_items(response):
    """Возвращает список объектов из paginated/non-paginated ответа."""
    if isinstance(response.data, dict) and 'results' in response.data:
        return response.data['results']

    return response.data


def aware_datetime(year, month, day):
    """Возвращает timezone-aware datetime для тестов."""
    return timezone.make_aware(datetime(year, month, day))


def create_catalog_filter_dataset():
    """Создает набор товаров для проверки фильтров каталога."""
    rock = GenreFactory(name='Rock', slug='rock')
    jazz = GenreFactory(name='Jazz', slug='jazz')

    tshirt = MerchKindFactory(name='Футболка', slug='tshirt')
    cap = MerchKindFactory(name='Кепка', slug='cap')
    vinyl = MerchKindFactory(
        name='Винил',
        slug='vinyl',
        is_carrier=True,
    )

    first_artist = ArtistProfileFactory(
        name='First Artist',
    )
    second_artist = ArtistProfileFactory(
        name='Second Artist',
    )

    rock_album = create_album_product(
        artist=first_artist,
        name='Rock Album',
        genre=rock,
    )
    jazz_album = create_album_product(
        artist=second_artist,
        name='Jazz Album',
        genre=jazz,
    )

    tshirt_merch = create_merch_product(
        artist=first_artist,
        name='T-Shirt',
        kind=tshirt,
    )
    cap_merch = create_merch_product(
        artist=second_artist,
        name='Cap',
        kind=cap,
    )

    rock_carrier = create_carrier_product(
        artist=first_artist,
        name='Rock Vinyl',
        album=rock_album.album,
        kind=vinyl,
    )
    jazz_carrier = create_carrier_product(
        artist=second_artist,
        name='Jazz Vinyl',
        album=jazz_album.album,
        kind=vinyl,
    )

    return {
        'rock': rock,
        'jazz': jazz,
        'tshirt': tshirt,
        'cap': cap,
        'vinyl': vinyl,
        'first_artist': first_artist,
        'second_artist': second_artist,
        'rock_album': rock_album,
        'jazz_album': jazz_album,
        'tshirt_merch': tshirt_merch,
        'cap_merch': cap_merch,
        'rock_carrier': rock_carrier,
        'jazz_carrier': jazz_carrier,
    }
