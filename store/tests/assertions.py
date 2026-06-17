"""Проверки контрактов API приложения store."""

PUBLIC_PRODUCT_CARD_KEYS = {
    'product_id',
    'name',
    'artist_name',
    'kind',
    'year',
    'price',
    'image',
    'is_favorite',
    'target',
}

PUBLIC_PRODUCT_CARD_TARGET_KEYS = {
    'type',
    'url',
    'selected_variant_id',
}

CATALOG_RELEASE_DETAIL_KEYS = {
    'id',
    'artist_name',
    'artist_image',
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

CATALOG_MERCH_DETAIL_KEYS = {
    'id',
    'name',
    'description',
    'price',
    'allow_overpay',
    'kind',
    'property_name',
    'stock',
    'variants',
    'artist_name',
    'artist_image',
    'images',
}

CATALOG_MERCH_VARIANT_KEYS = {
    'sku',
    'stock',
    'variant_id',
    'property_value',
}

CATALOG_MERCH_IMAGE_KEYS = {
    'id',
    'image',
    'is_main',
}


def assert_public_product_card_contract(card):
    """Проверяет базовый контракт публичной карточки товара."""
    assert set(card) == PUBLIC_PRODUCT_CARD_KEYS
    assert set(card['target']) == PUBLIC_PRODUCT_CARD_TARGET_KEYS

    assert isinstance(card['product_id'], int)
    assert isinstance(card['name'], str)
    assert isinstance(card['artist_name'], str)
    assert isinstance(card['kind'], str)
    assert isinstance(card['year'], int) or card['year'] is None
    assert isinstance(card['price'], str)
    assert isinstance(card['is_favorite'], bool)
    assert card['image'] is None or isinstance(card['image'], str)
    assert isinstance(card['target']['type'], str)
    assert isinstance(card['target']['url'], str)
    assert (
        isinstance(card['target']['selected_variant_id'], int)
        or card['target']['selected_variant_id'] is None
    )


def assert_catalog_release_detail_contract(data):
    """Проверяет контракт витринной detail-карточки релиза."""
    assert set(data) == CATALOG_RELEASE_DETAIL_KEYS

    assert isinstance(data['id'], int)
    assert isinstance(data['artist_name'], str)
    assert data['artist_image'] is None or isinstance(
        data['artist_image'],
        str,
    )
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
    """Проверяет контракт витринной detail-карточки мерча."""
    assert set(data) == CATALOG_MERCH_DETAIL_KEYS

    assert isinstance(data['id'], int)
    assert isinstance(data['name'], str)
    assert isinstance(data['description'], str)
    assert isinstance(data['price'], str)
    assert isinstance(data['allow_overpay'], bool)
    assert isinstance(data['kind'], str)
    assert isinstance(data['property_name'], str)
    assert data['stock'] is None or isinstance(data['stock'], int)
    assert data['artist_name'] is None or isinstance(data['artist_name'], str)
    assert data['artist_image'] is None or isinstance(
        data['artist_image'],
        str,
    )
    assert isinstance(data['images'], list)
    assert isinstance(data['variants'], list)

    for image in data['images']:
        assert set(image) == CATALOG_MERCH_IMAGE_KEYS
        assert isinstance(image['id'], int)
        assert isinstance(image['image'], str)
        assert isinstance(image['is_main'], bool)

    for variant in data['variants']:
        assert_catalog_merch_variant_contract(variant)


def assert_catalog_merch_variant_contract(variant):
    """Проверяет контракт варианта обычного мерча."""
    assert set(variant) == CATALOG_MERCH_VARIANT_KEYS

    assert isinstance(variant['variant_id'], int)
    assert isinstance(variant['sku'], str)
    assert variant['stock'] is None or isinstance(variant['stock'], int)
    assert isinstance(variant['property_value'], str)
