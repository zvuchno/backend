"""Сценарии создания тестовых данных магазина."""

from decimal import Decimal

from django.utils import timezone

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
from users.tests.factories import ArtistUserFactory


def create_album_product(
    *,
    owner=None,
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
    owner = owner or ArtistUserFactory()

    if artist_name:
        owner.artist_profile.name = artist_name
        owner.artist_profile.save(update_fields=('name', 'slug'))

    album = AlbumFactory(
        owner=owner,
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
    owner=None,
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
    owner = owner or ArtistUserFactory()

    if artist_name:
        owner.artist_profile.name = artist_name
        owner.artist_profile.save(update_fields=('name', 'slug'))

    merch = MerchFactory(
        owner=owner,
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
        MerchImageFactory(merch=merch, is_main=True)

    return product


def create_carrier_product(
    *,
    owner=None,
    artist_name=None,
    album=None,
    genre=None,
    kind=None,
    name='Тестовый винил',
    price=Decimal('2500.00'),
    with_variant=True,
):
    """Создает физический носитель, связанный с альбомом."""
    owner = owner or ArtistUserFactory()

    if album is None:
        album = AlbumFactory(
            owner=owner,
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
        owner=owner,
        artist_name=artist_name,
        kind=carrier_kind,
        name=name,
        price=price,
        album=album,
        with_variant=with_variant,
    )


def set_created_at(instance, value=None):
    """Принудительно задает created_at для проверки сортировок."""
    value = value or timezone.now()
    type(instance).objects.filter(pk=instance.pk).update(created_at=value)
    instance.refresh_from_db(fields=('created_at',))
    return instance


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


def create_catalog_filter_dataset():
    """Создает набор товаров для проверки фильтров genre и kind."""
    rock = GenreFactory(name='Rock', slug='rock')
    jazz = GenreFactory(name='Jazz', slug='jazz')
    tshirt = MerchKindFactory(name='Футболка', slug='tshirt')
    cap = MerchKindFactory(name='Кепка', slug='cap')

    rock_album = create_album_product(name='Rock Album', genre=rock)
    jazz_album = create_album_product(name='Jazz Album', genre=jazz)
    tshirt_merch = create_merch_product(name='T-Shirt', kind=tshirt)
    cap_merch = create_merch_product(name='Cap', kind=cap)

    return {
        'rock': rock,
        'jazz': jazz,
        'tshirt': tshirt,
        'cap': cap,
        'rock_album': rock_album,
        'jazz_album': jazz_album,
        'tshirt_merch': tshirt_merch,
        'cap_merch': cap_merch,
    }


# def create_catalog_sorting_dataset():
#     """Создает набор товаров для проверки сортировок."""
#     cheap = create_album_product(
#         name='Cheap Album',
#         price=Decimal('100.00'),
#     )
#     middle = create_merch_product(
#         name='Middle Merch',
#         price=Decimal('500.00'),
#     )
#     expensive = create_album_product(
#         name='Expensive Album',
#         price=Decimal('900.00'),
#     )
#
#     return {
#         'cheap': cheap,
#         'middle': middle,
#         'expensive': expensive,
#     }


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


def get_product_titles(response):
    """Возвращает названия товаров из paginated-ответа каталога."""
    return [item['title'] for item in response.data['results']]


def get_response_items(response):
    """Возвращает список объектов из paginated/non-paginated ответа."""
    if isinstance(response.data, dict) and 'results' in response.data:
        return response.data['results']

    return response.data
