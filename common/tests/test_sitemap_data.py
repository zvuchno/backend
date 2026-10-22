from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache, caches
from django.core.cache.backends.dummy import DummyCache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from store.models import Album, Merch
from store.tests.scenarios import (
    create_album_product,
    create_carrier_product,
    create_merch_product,
)
from users.models import ArtistProfile

pytestmark = pytest.mark.django_db


# =================================
# Fixtures
# =================================
@pytest.fixture(autouse=True)
def sitemap_env(publication_readiness_enabled):
    """Включает проверку готовности и чистит кеш между тестами."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def artist(ready_physical_artist_user):
    """Профиль артиста, готового к цифровым и физическим продажам."""
    return ready_physical_artist_user.artist_profile


@pytest.fixture
def fetch(api_client, sitemap_url):
    """Возвращает функцию запроса sitemap анонимным клиентом."""

    def _fetch() -> list[dict]:
        response = api_client.get(sitemap_url)
        assert response.status_code == 200
        return response.json()

    return _fetch


# =================================
# Helpers
# =================================
def keys(entries):
    """Приводит записи к множеству (type, id, slug) для сравнения."""
    return {(e['type'], e['id'], e['slug']) for e in entries}


def release_key(product):
    """Ключ записи релиза в выдаче sitemap."""
    return ('release', product.album_id, None)


def merch_key(product):
    """Ключ записи мерча в выдаче sitemap."""
    return ('merch', product.merch_id, None)


def artist_key(artist):
    """Ключ записи артиста в выдаче sitemap."""
    return ('artist', None, artist.slug)


# =================================
# Контракт ответа
# =================================
def test_empty_when_no_public_content(fetch):
    """Без публичного контента отдаётся пустой список."""
    assert fetch() == []


def test_entry_has_expected_fields(fetch, artist):
    """Запись содержит ровно type, id, slug и валидную дату lastmod."""
    create_album_product(artist=artist)

    entry = fetch()[0]

    assert set(entry) == {'type', 'id', 'slug', 'lastmod'}
    assert parse_datetime(entry['lastmod']) is not None


def test_full_set_contains_each_page_once(fetch, artist):
    """Артист, релиз и мерч дают три уникальные записи."""
    album = create_album_product(artist=artist)
    merch = create_merch_product(artist=artist)

    entries = fetch()

    assert len(entries) == len(keys(entries)) == 3
    assert keys(entries) == {
        release_key(album),
        merch_key(merch),
        artist_key(artist),
    }


# =================================
# Релизы
# =================================
def test_public_release_is_listed(fetch, artist):
    """Опубликованный релиз попадает в sitemap по id альбома."""
    product = create_album_product(artist=artist)

    assert release_key(product) in keys(fetch())


@pytest.mark.parametrize(
    'days_offset',
    [None, -1],
    ids=['no_release_date', 'past_release_date'],
)
def test_release_with_available_date_is_listed(fetch, artist, days_offset):
    """Релиз без даты выхода или с уже наступившей датой виден."""
    product = create_album_product(artist=artist)
    release_date = (
        None
        if days_offset is None
        else timezone.localdate() + timedelta(days=days_offset)
    )
    Album.objects.filter(pk=product.album_id).update(
        release_date=release_date,
    )

    assert release_key(product) in keys(fetch())


@pytest.mark.parametrize(
    'overrides',
    [
        {'is_published': False},
        {'visibility': 'hidden'},
        {'visibility': 'link_only'},
        {'price': Decimal('0.00')},
    ],
    ids=['not_published', 'hidden', 'link_only', 'zero_price'],
)
def test_non_public_release_is_excluded(fetch, artist, overrides):
    """Неопубликованные, скрытые и бесплатные релизы не попадают в карту."""
    product = create_album_product(artist=artist, **overrides)

    assert release_key(product) not in keys(fetch())


def test_inactive_release_is_excluded(fetch, artist):
    """Неактивный альбом скрыт."""
    product = create_album_product(artist=artist)
    Album.objects.filter(pk=product.album_id).update(is_active=False)

    assert release_key(product) not in keys(fetch())


def test_release_with_future_date_is_excluded(fetch, artist):
    """Релиз с датой выхода в будущем не попадает в карту."""
    product = create_album_product(artist=artist)
    Album.objects.filter(pk=product.album_id).update(
        release_date=timezone.localdate() + timedelta(days=1),
    )

    assert release_key(product) not in keys(fetch())


def test_release_of_not_ready_artist_is_excluded(
    fetch,
    ready_physical_artist_user,
):
    """Релиз артиста без подтверждённого email не попадает в карту."""
    user = ready_physical_artist_user
    product = create_album_product(artist=user.artist_profile)
    user.is_email_verified = False
    user.save(update_fields=('is_email_verified',))

    assert release_key(product) not in keys(fetch())


# =================================
# Мерч
# =================================
def test_public_merch_is_listed(fetch, artist):
    """Обычный мерч в наличии попадает в sitemap по id мерча."""
    product = create_merch_product(artist=artist)

    assert merch_key(product) in keys(fetch())


def test_merch_linked_to_album_is_listed(fetch, artist):
    """Мерч, привязанный к альбому, но не носитель → отдельная запись."""
    album = create_album_product(artist=artist)
    product = create_merch_product(artist=artist, album=album.album)

    assert merch_key(product) in keys(fetch())


@pytest.mark.parametrize(
    'overrides',
    [
        {'is_published': False},
        {'visibility': 'hidden'},
        {'visibility': 'link_only'},
        {'price': Decimal('0.00')},
        {'with_variant': False},
    ],
    ids=['not_published', 'hidden', 'link_only', 'zero_price', 'no_variant'],
)
def test_non_public_merch_is_excluded(fetch, artist, overrides):
    """Неопубликованный, скрытый, бесплатный и недоступный мерч скрыт."""
    product = create_merch_product(artist=artist, **overrides)

    assert merch_key(product) not in keys(fetch())


def test_inactive_merch_is_excluded(fetch, artist):
    """Неактивный мерч скрыт."""
    product = create_merch_product(artist=artist)
    Merch.objects.filter(pk=product.merch_id).update(is_active=False)

    assert merch_key(product) not in keys(fetch())


def test_merch_without_shipping_is_excluded(
    fetch,
    ready_artist_user,
):
    """Мерч артиста без настроенной доставки не попадает в карту."""
    product = create_merch_product(artist=ready_artist_user.artist_profile)

    assert merch_key(product) not in keys(fetch())


def test_carrier_is_covered_by_release_page(fetch, artist):
    """Носитель альбома отдельной записью не идёт → релиз один раз."""
    album = create_album_product(artist=artist)
    create_carrier_product(artist=artist, album=album.album)

    entries = fetch()

    assert not [e for e in entries if e['type'] == 'merch']
    releases = [e for e in entries if e['type'] == 'release']
    assert [e['id'] for e in releases] == [album.album_id]


# =================================
# Артисты
# =================================
def test_artist_is_listed_by_slug(fetch, artist):
    """Готовый артист попадает в sitemap по slug, без id."""
    assert artist_key(artist) in keys(fetch())


def test_inactive_artist_is_excluded(fetch, artist):
    """Неактивный артист скрыт."""
    ArtistProfile.objects.filter(pk=artist.pk).update(is_active=False)

    assert artist_key(artist) not in keys(fetch())


def test_artist_without_cover_is_excluded(fetch, artist):
    """Артист без обложки профиля не готов к публичному показу."""
    ArtistProfile.objects.filter(pk=artist.pk).update(cover='')

    assert artist_key(artist) not in keys(fetch())


def test_artist_with_unverified_email_is_excluded(
    fetch,
    ready_physical_artist_user,
):
    """Артист с неподтверждённым email скрыт."""
    user = ready_physical_artist_user
    user.is_email_verified = False
    user.save(update_fields=('is_email_verified',))

    assert artist_key(user.artist_profile) not in keys(fetch())


def test_label_created_artist_is_listed(
    fetch,
    ready_label_user,
    label_created_artist,
):
    """Артист без аккаунта виден, если лейбл готов к публикации."""
    assert artist_key(label_created_artist) in keys(fetch())


def test_label_created_artist_is_excluded_when_label_not_ready(
    fetch,
    label_user,
    label_created_artist,
):
    """Артист лейбла скрыт, пока лейбл не подтвердил email и данные."""
    assert artist_key(label_created_artist) not in keys(fetch())


# =================================
# Производительность и кеш
# =================================
def test_number_of_queries_does_not_grow_with_data(
    fetch,
    artist,
    django_assert_max_num_queries,
):
    """Число запросов не зависит от количества записей (нет N+1)."""
    for _ in range(10):
        create_album_product(artist=artist)
        create_merch_product(artist=artist)
    with django_assert_max_num_queries(20):
        fetch()


def test_response_is_cached(fetch, artist):
    """Повторный запрос отдаётся из кеша, после очистки кеша обновляется."""
    if isinstance(caches['default'], DummyCache):
        pytest.skip('В тестовых настройках кеш отключён (DummyCache).')

    create_album_product(artist=artist)
    first = fetch()

    create_album_product(artist=artist)
    assert keys(fetch()) == keys(first)

    cache.clear()
    assert len(fetch()) == len(first) + 1
