"""Тесты глобального поиска по каталогу (CatalogSearch).

Требуют DB Postgres
запуск: pytest -m postgres
(docker compose exec backend pytest
 store/tests/test_catalog_search.py -m postgres)
"""

import pytest
from django.core.files.base import ContentFile
from django.db import connection
from django.urls import reverse

from store.models import Product
from store.tests.factories import GenreFactory
from store.tests.scenarios import (
    create_album_product,
    create_merch_product,
)
from users.tests.factories import ArtistProfileFactory

CATALOG_SEARCH_URL_NAME = 'api:store:catalog-search'


@pytest.fixture
def catalog_search_url():
    """Возвращает URL глобального поиска по каталогу."""
    return reverse(CATALOG_SEARCH_URL_NAME)


@pytest.fixture
def refresh_catalog_search(db):
    """Обновляет materialized view catalog_search."""

    def _refresh() -> None:
        with connection.cursor() as cursor:
            cursor.execute('REFRESH MATERIALIZED VIEW catalog_search;')

    return _refresh


def do_search(api_client, catalog_search_url, query):
    """Выполняет запрос поиска, проверяет 200 и возвращает response."""
    response = api_client.get(catalog_search_url, {'q': query})
    assert response.status_code == 200
    return response


def response_items(response):
    """Возвращает список элементов из paginated/non-paginated ответа."""
    if isinstance(response.data, dict) and 'results' in response.data:
        return response.data['results']

    return response.data


def response_names(response):
    """Возвращает список name из результатов поиска."""
    return [item['name'] for item in response_items(response)]


def find_item(response, name):
    """Возвращает элемент ответа по точному совпадению name."""
    return next(
        item for item in response_items(response) if item['name'] == name
    )


# =================================
# Пустой / некорректный запрос
# =================================
@pytest.mark.postgres
@pytest.mark.django_db
class TestCatalogSearchEmptyQuery:
    """Поведение при пустом или отсутствующем поисковом запросе."""

    def test_empty_string_returns_no_results(
        self,
        api_client,
        catalog_search_url,
    ):
        """Пустая строка не должна возвращать весь каталог и падать."""
        response = do_search(api_client, catalog_search_url, '')

        assert response_names(response) == []

    def test_missing_param_returns_no_results(
        self,
        api_client,
        catalog_search_url,
    ):
        """Отсутствие параметра search обрабатывается так же, как пустой."""
        response = api_client.get(catalog_search_url)

        assert response.status_code == 200
        assert response_names(response) == []

    def test_whitespace_only_query_returns_no_results(
        self,
        api_client,
        catalog_search_url,
    ):
        """Строка из одних пробелов трактуется как пустой запрос."""
        response = do_search(api_client, catalog_search_url, '   ')

        assert response_names(response) == []


# =================================
# Альбомы
# =================================
@pytest.mark.postgres
@pytest.mark.django_db
@pytest.mark.usefixtures('publication_readiness_disabled')
class TestCatalogSearchAlbum:
    """Поиск альбомов."""

    def test_finds_album_by_exact_name(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """Альбом находится по точному совпадению названия."""
        create_album_product(name='Clouds')
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Clouds')

        assert 'Clouds' in response_names(response)

    def test_finds_album_by_artist_name(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """Альбом находится по имени артиста, а не только по названию."""
        artist = ArtistProfileFactory(name='Molchat Doma')
        create_album_product(artist=artist, name='Etazhi')
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Molchat')

        assert 'Etazhi' in response_names(response)

    def test_finds_album_by_genre_name(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """Альбом находится по названию жанра."""
        genre = GenreFactory(name='Synthpop')
        create_album_product(name='Night Drive', genre=genre)
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Synthpop')

        assert 'Night Drive' in response_names(response)

    def test_unpublished_album_excluded(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """Неопубликованный альбом не попадает в индекс."""
        create_album_product(name='Draft Album', is_published=False)
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Draft')

        assert response_names(response) == []

    def test_hidden_album_excluded(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """Альбом с visibility=hidden не найдётся через глобальный поиск."""
        create_album_product(name='Secret Album', visibility='hidden')
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Secret')

        assert response_names(response) == []

    def test_album_target_points_to_its_own_release(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """Таргет альбома — карточка релиза с id самого альбома."""
        product = create_album_product(name='Target Test Album')
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Target Test')
        item = find_item(response, 'Target Test Album')

        assert item['target']['type'] == 'release'
        assert item['target']['id'] == product.album_id
        assert item['target']['url'] == reverse(
            'api:store:catalog-release-detail',
            args=(product.album_id,),
        )


# =================================
# Треки
# =================================
@pytest.mark.postgres
@pytest.mark.django_db
@pytest.mark.usefixtures('publication_readiness_disabled')
class TestCatalogSearchTrack:
    """Поиск треков."""

    def test_finds_track_by_name(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
        variant_factory,
        artist_user,
    ):
        """Трек с ненулевой ценой находится по названию."""
        variant_factory(
            'track',
            artist=artist_user.artist_profile,
            name='Redemption Song',
            price=500,
        )
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Redemption')

        assert 'Redemption Song' in response_names(response)

    def test_track_target_points_to_its_album_not_itself(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
        variant_factory,
        artist_user,
    ):
        """Таргет трека — карточка релиза его альбома (album_id)."""
        variant = variant_factory(
            'track',
            artist=artist_user.artist_profile,
            name='Album Bound Track',
            price=500,
        )
        album = variant.product.track.album
        refresh_catalog_search()

        response = do_search(
            api_client,
            catalog_search_url,
            'Album Bound',
        )
        item = find_item(response, 'Album Bound Track')

        assert item['target']['type'] == 'release'
        assert item['target']['id'] == album.id
        assert item['target']['url'] == reverse(
            'api:store:catalog-release-detail',
            args=(album.id,),
        )

    def test_free_track_excluded(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
        variant_factory,
        artist_user,
    ):
        """Бесплатный трек (price=0) не попадает в поиск."""
        variant = variant_factory(
            'track',
            artist=artist_user.artist_profile,
            name='Free Bonus Track',
        )
        Product.objects.filter(pk=variant.product_id).update(price=0)
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Free Bonus')

        assert response_names(response) == []


# =================================
# Мерч
# =================================
@pytest.mark.postgres
@pytest.mark.django_db
@pytest.mark.usefixtures('publication_readiness_disabled')
class TestCatalogSearchMerch:
    """Поиск мерча."""

    def test_finds_merch_with_shipping_point(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
        artist_user,
    ):
        """Мерч артиста с настроенным ПВЗ отправления находится в поиске."""
        create_merch_product(
            artist=artist_user.artist_profile,
            name='Tour Hoodie',
        )
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Hoodie')

        assert 'Tour Hoodie' in response_names(response)

    def test_merch_without_shipping_point_excluded(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
        artist_without_shipping_point,
    ):
        """Мерч артиста без ПВЗ отправления не попадает в поиск."""
        create_merch_product(
            artist=artist_without_shipping_point.artist_profile,
            name='Undeliverable Cap',
        )
        refresh_catalog_search()

        response = do_search(
            api_client,
            catalog_search_url,
            'Undeliverable',
        )

        assert response_names(response) == []

    def test_out_of_stock_merch_excluded(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
        artist_user,
        variant_factory,
    ):
        """Мерч с нулевым остатком не попадает в поиск."""
        variant_factory(
            'merch',
            artist=artist_user.artist_profile,
            name='Sold Out Tee',
            stock=0,
        )
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Sold Out')

        assert response_names(response) == []

    def test_merch_target_points_to_its_own_detail(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
        artist_user,
    ):
        """Таргет мерча — карточка мерча с его собственным id."""
        product = create_merch_product(
            artist=artist_user.artist_profile,
            name='Target Merch Item',
        )
        refresh_catalog_search()

        response = do_search(
            api_client,
            catalog_search_url,
            'Target Merch',
        )
        item = find_item(response, 'Target Merch Item')

        assert item['target']['type'] == 'merch'
        assert item['target']['id'] == product.merch_id
        assert item['target']['url'] == reverse(
            'api:store:catalog-merch-detail',
            args=(product.merch_id,),
        )


# =================================
# Артисты, жанры, типы мерча
# =================================
@pytest.mark.postgres
@pytest.mark.django_db
class TestCatalogSearchReferenceEntities:
    """Поиск по справочным сущностям без товаров."""

    def test_finds_active_artist_by_name(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """Активный артист находится по имени, даже без единого товара."""
        ArtistProfileFactory(name='Standalone Artist', is_active=True)
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Standalone')

        assert 'Standalone Artist' in response_names(response)

    def test_inactive_artist_excluded(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """Неактивный (заблокированный) артист не попадает в поиск."""
        ArtistProfileFactory(name='Banned Artist', is_active=False)
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Banned')

        assert response_names(response) == []

    def test_artist_target_points_to_public_profile(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """Таргет артиста ведёт на его публичный профиль."""
        artist = ArtistProfileFactory(name='Linked Artist', is_active=True)
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Linked')
        item = find_item(response, 'Linked Artist')

        assert item['target']['type'] == 'artist'
        assert item['target']['id'] == artist.id
        assert item['target']['url'] == reverse(
            'api:users:artist_public',
            args=(artist.slug,),
        )


# =================================
# Опечатки (trigram similarity)
# =================================
@pytest.mark.postgres
@pytest.mark.django_db
@pytest.mark.usefixtures('publication_readiness_disabled')
class TestCatalogSearchFuzzyMatch:
    """Поиск с опечатками через триграммное сходство."""

    def test_finds_result_despite_small_typo(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """Небольшая опечатка в запросе всё равно находит результат."""
        create_album_product(name='Midnight City')
        refresh_catalog_search()

        response = do_search(
            api_client,
            catalog_search_url,
            'Midnigt City',
        )

        assert 'Midnight City' in response_names(response)

    def test_unrelated_query_returns_nothing(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """Запрос, не похожий ни на что, не даёт ложных срабатываний."""
        create_album_product(name='Midnight City')
        refresh_catalog_search()

        response = do_search(
            api_client,
            catalog_search_url,
            'Zzxqvw Unrelated Query',
        )

        assert response_names(response) == []


# =================================
# Готовность артиста к публикации (54-ФЗ)
# =================================
@pytest.mark.postgres
@pytest.mark.django_db
@pytest.mark.usefixtures('publication_readiness_enabled')
class TestCatalogSearchPublicationReadiness:
    """Фильтрация по готовности артиста к публикации."""

    def test_ready_artist_album_included(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
        ready_artist_factory,
    ):
        """Альбом артиста, готового к публикации, находится в поиске."""
        artist = ready_artist_factory(name='Ready Artist')
        create_album_product(artist=artist, name='Ready Album')
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Ready Album')

        assert 'Ready Album' in response_names(response)

    def test_not_ready_artist_album_excluded(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """Альбом артиста без подтверждённых email/юр. профиля скрыт."""
        artist = ArtistProfileFactory(name='Unverified Artist')
        create_album_product(artist=artist, name='Hidden By Readiness')
        refresh_catalog_search()

        response = do_search(
            api_client,
            catalog_search_url,
            'Hidden By Readiness',
        )

        assert response_names(response) == []


# =================================
# Изображение
# =================================
@pytest.mark.postgres
@pytest.mark.django_db
@pytest.mark.usefixtures('publication_readiness_disabled')
class TestCatalogSearchImage:
    """Формирование ссылки на изображение в ответе поиска."""

    def test_album_cover_returns_absolute_url(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """Image в ответе — абсолютный URL, а не сырой относительный путь."""
        product = create_album_product(name='Cover Test Album')
        product.album.cover_image.save(
            'cover.webp',
            ContentFile(b'fake-cover-bytes'),
            save=True,
        )
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'Cover Test')
        item = find_item(response, 'Cover Test Album')

        assert item['image'] is not None
        assert item['image'].startswith('http')

    def test_album_without_cover_returns_null(
        self,
        api_client,
        catalog_search_url,
        refresh_catalog_search,
    ):
        """У альбома без обложки image равен null, без ошибки на бэке."""
        create_album_product(name='No Cover Album')
        refresh_catalog_search()

        response = do_search(api_client, catalog_search_url, 'No Cover')
        item = find_item(response, 'No Cover Album')

        assert item['image'] is None
