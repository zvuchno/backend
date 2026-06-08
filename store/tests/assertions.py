"""Проверки контрактов API приложения store."""

CATALOG_CARD_KEYS = {
    'name',
    'artist_name',
    'kind',
    'year',
    'price',
    'image',
    'is_favorite',
    'target',
}

CATALOG_CARD_TARGET_KEYS = {
    'type',
    'url',
    'selected_variant_id',
}

CATALOG_RELEASE_DETAIL_KEYS = {
    'id',
    'artist_name',
    'is_single',
    'variants',
}

CATALOG_RELEASE_VARIANT_KEYS = {
    'variant_id',
    'sku',
    'stock',
    'property_value',
    'name',
    'price',
    'allow_overpay',
    'description',
    'images',
}

CATALOG_MERCH_DETAIL_FORBIDDEN_KEYS = {
    'album',
    'visibility',
    'is_published',
    'images_merch',
}


def get_response_items(response):
    """Возвращает список объектов из paginated/non-paginated ответа."""
    if isinstance(response.data, dict) and 'results' in response.data:
        return response.data['results']

    return response.data


def assert_catalog_card_contract(card):
    """Проверяет контракт карточки публичного каталога."""
    assert set(card) == CATALOG_CARD_KEYS

    assert isinstance(card['name'], str)
    assert isinstance(card['artist_name'], str)
    assert card['kind'] is None or isinstance(card['kind'], str)
    assert card['year'] is None or isinstance(card['year'], int)
    assert isinstance(card['price'], str)
    assert card['image'] is None or isinstance(card['image'], str)
    assert isinstance(card['is_favorite'], bool)

    assert_catalog_card_target_contract(card['target'])


def assert_catalog_card_target_contract(target):
    """Проверяет контракт данных для перехода из карточки."""
    assert isinstance(target, dict)
    assert set(target) == CATALOG_CARD_TARGET_KEYS

    assert target['type'] in ('release', 'merch')
    assert isinstance(target['url'], str)
    assert target['selected_variant_id'] is None or isinstance(
        target['selected_variant_id'],
        int,
    )


def assert_catalog_release_detail_contract(data):
    """Проверяет контракт витринной detail-карточки релиза."""
    assert set(data) == CATALOG_RELEASE_DETAIL_KEYS

    assert isinstance(data['id'], int)
    assert isinstance(data['artist_name'], str)
    assert isinstance(data['is_single'], bool)
    assert isinstance(data['variants'], list)

    for variant in data['variants']:
        assert_catalog_release_variant_contract(variant)


def assert_catalog_release_variant_contract(variant):
    """Проверяет контракт варианта покупки релиза."""
    assert set(variant) == CATALOG_RELEASE_VARIANT_KEYS

    assert isinstance(variant['variant_id'], int)
    assert variant['sku'] is None or isinstance(variant['sku'], str)
    assert variant['stock'] is None or isinstance(variant['stock'], int)
    assert isinstance(variant['property_value'], str)
    assert isinstance(variant['name'], str)
    assert isinstance(variant['price'], str)
    assert isinstance(variant['allow_overpay'], bool)
    assert isinstance(variant['description'], str)
    assert isinstance(variant['images'], list)


def assert_catalog_merch_detail_contract(data):
    """Проверяет базовый контракт витринной detail-карточки мерча."""
    for key in CATALOG_MERCH_DETAIL_FORBIDDEN_KEYS:
        assert key not in data

    assert 'id' in data
    assert 'name' in data
    assert 'artist_name' in data
    assert 'images' in data
    assert 'variants' in data

    assert isinstance(data['id'], int)
    assert isinstance(data['name'], str)
    assert data['artist_name'] is None or isinstance(
        data['artist_name'],
        str,
    )
    assert isinstance(data['images'], list)
    assert isinstance(data['variants'], list)

    for variant in data['variants']:
        assert_catalog_merch_variant_contract(variant)


def assert_catalog_merch_variant_contract(variant):
    """Проверяет контракт варианта обычного мерча."""
    assert 'variant_id' in variant
    assert 'property_value' in variant

    assert 'id' not in variant
    assert 'value' not in variant

    assert isinstance(variant['variant_id'], int)
    assert isinstance(variant['property_value'], str)
