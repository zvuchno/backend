"""Тесты импорта цифровых Product для mapped Album и Track."""

from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from catalog_migration.services.catalog_bundle import (
    bundle_root,
    mapping_version,
)
from catalog_migration.services.catalog_digital_product_import import (
    CatalogDigitalProductImportError,
    CatalogDigitalProductImporter,
)
from catalog_migration.services.catalog_migration_preflight import (
    BUNDLE_DIRECTORY,
    BUNDLE_VERSION,
)
from catalog_migration.services.catalog_profile_import import (
    CatalogProfileImporter,
)
from catalog_migration.services.catalog_release_import import (
    CatalogReleaseImporter,
)
from catalog_migration.services.catalog_track_import import (
    CatalogTrackImporter,
)
from catalog_migration.tests.test_catalog_migration_preflight import (
    _code,
    _load,
    _make_package,
    _write_json,
)
from catalog_migration.tests.v2_package import v2_package

from store.constants import CHAR_PRESET_DIGITAL, ZERO_MONEY
from store.models import (
    Album,
    CatalogMigrationMapping,
    Product,
    ProductVariant,
    Track,
)
from users.models import ArtistProfile


def _prepare_package(tmp_path: Path, *profile_indexes: int) -> Path:
    package = _make_package(tmp_path)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    config['artist_code_whitelist'] = [
        _code(index) for index in profile_indexes
    ]
    _write_json(config_path, config)

    releases_path = package / BUNDLE_DIRECTORY / 'data' / 'releases.json'
    releases = _load(releases_path)
    for index, row in enumerate(releases):
        price = f'{100 + index}.00'
        row.update({
            'source_price': price,
            'target_price': price,
            'price_status': 'PRESERVED_ACCEPTED_PRICE',
            'price_requires_review': False,
            'price_policy': {
                'source_price': price,
                'target_price': price,
                'price_status': 'PRESERVED_ACCEPTED_PRICE',
                'requires_review': False,
            },
        })
    _write_json(releases_path, releases)
    return package


def _map(entity_type: str, entity_id: str, target: Any) -> None:
    CatalogMigrationMapping.objects.create(
        bundle_version=BUNDLE_VERSION,
        entity_type=entity_type,
        source_entity_id=entity_id,
        django_pk=target.pk,
    )


def _create_content(index: int = 0) -> tuple[ArtistProfile, Album, Track]:
    artist = ArtistProfile.objects.create(
        name=f'Profile {index}',
        slug=_code(index).lower(),
    )
    _map(
        CatalogMigrationMapping.EntityType.PROFILE,
        f'profile-{index:02d}',
        artist,
    )
    album = Album.objects.bulk_create([
        Album(
            artist=artist,
            name=f'Release {index}',
            is_published=False,
            created_by=None,
            payout_recipient=None,
        ),
    ])[0]
    _map(
        CatalogMigrationMapping.EntityType.RELEASE,
        f'release-{index:02d}',
        album,
    )
    track = Track.objects.bulk_create([
        Track(
            album=album,
            name=f'Track {index}',
            position=1,
            created_by=None,
        ),
    ])[0]
    _map(
        CatalogMigrationMapping.EntityType.TRACK,
        f'track-{index:02d}',
        track,
    )
    return artist, album, track


@pytest.mark.django_db
def test_creates_album_and_zero_price_track_via_product_service(
    tmp_path,
    monkeypatch,
):
    """Штатный сервис создаёт оба Product и их технические варианты."""
    package = _prepare_package(tmp_path, 0)
    artist, album, track = _create_content()
    calls = []
    from store.services.commerce import ProductService

    original = ProductService.ensure_commerce.__func__

    def spy(cls, content, validated_data) -> Product:
        calls.append((content.pk, validated_data.copy()))
        return original(cls, content, validated_data)

    monkeypatch.setattr(ProductService, 'ensure_commerce', classmethod(spy))

    result = CatalogDigitalProductImporter(package).run()

    assert result.created_products == 2
    assert result.created_variants == 2
    assert len(calls) == 2
    album_product = Product.objects.get(album=album)
    track_product = Product.objects.get(track=track)
    assert album_product.price == Decimal('100.0000')
    assert track_product.price == ZERO_MONEY
    for product in (album_product, track_product):
        variant = product.variants.get()
        assert variant.property_value == CHAR_PRESET_DIGITAL
        assert variant.stock is None
        assert variant.is_active is True
        assert variant.sku
    assert track_product.variants.get().is_available_for_purchase is False
    assert album.is_published is False
    assert album.created_by_id is None
    assert album.payout_recipient_id is None
    assert track.created_by_id is None
    assert get_user_model().objects.count() == 0
    assert (
        CatalogMigrationMapping.objects.filter(
            entity_type=CatalogMigrationMapping.EntityType.PRODUCT,
        ).count()
        == 2
    )
    assert (
        CatalogMigrationMapping.objects.filter(
            entity_type=CatalogMigrationMapping.EntityType.VARIANT,
        ).count()
        == 2
    )
    assert artist.pk == album.artist_id


@pytest.mark.django_db
def test_adopts_unambiguously_existing_product_without_changes(tmp_path):
    """Товар точного mapped-контента принимается без вызова update-path."""
    package = _prepare_package(tmp_path, 0)
    _, album, track = _create_content()
    product = Product.objects.create(
        album=album,
        price=Decimal('777.0000'),
        allow_overpay=True,
        property_name='Ручное значение',
    )
    variant = ProductVariant.objects.create(
        product=product,
        property_value=CHAR_PRESET_DIGITAL,
        stock=None,
        is_active=False,
    )

    result = CatalogDigitalProductImporter(package).run()

    product.refresh_from_db()
    variant.refresh_from_db()
    assert result.adopted_products == 1
    assert result.created_products == 1  # Track.
    assert Product.objects.count() == 2
    assert product.price == Decimal('777.0000')
    assert product.allow_overpay is True
    assert product.property_name == 'Ручное значение'
    assert variant.is_active is False
    assert (
        CatalogMigrationMapping.objects.get(
            entity_type=CatalogMigrationMapping.EntityType.PRODUCT,
            source_entity_id='release-00',
        ).django_pk
        == product.pk
    )
    assert Product.objects.filter(track=track).exists()


@pytest.mark.django_db
def test_repeated_import_preserves_human_changes(tmp_path):
    """Повторный запуск не обновляет mapped Product и Variant."""
    package = _prepare_package(tmp_path, 0)
    _, album, _ = _create_content()
    CatalogDigitalProductImporter(package).run()
    product = Product.objects.get(album=album)
    variant = product.variants.get()
    product.price = Decimal('999.0000')
    product.save(update_fields=('price',))
    variant.is_active = False
    variant.save(update_fields=('is_active',))

    result = CatalogDigitalProductImporter(package).run()

    product.refresh_from_db()
    variant.refresh_from_db()
    assert result.created_products == 0
    assert result.adopted_products == 0
    assert result.already_mapped == 2
    assert Product.objects.count() == 2
    assert ProductVariant.objects.count() == 2
    assert product.price == Decimal('999.0000')
    assert variant.is_active is False


@pytest.mark.django_db
def test_manual_product_without_digital_variant_blocks_all_writes(tmp_path):
    """Неоднозначный ручной товар блокирует этап до первого создания."""
    package = _prepare_package(tmp_path, 0)
    _, album, _ = _create_content()
    product = Product.objects.create(album=album, price=123)
    ProductVariant.objects.create(
        product=product,
        property_value='manual',
        stock=1,
    )

    with pytest.raises(
        CatalogDigitalProductImportError,
        match='не имеет однозначного digital-варианта.*release-00',
    ):
        CatalogDigitalProductImporter(package).run()

    assert Product.objects.count() == 1
    assert not CatalogMigrationMapping.objects.filter(
        entity_type__in=(
            CatalogMigrationMapping.EntityType.PRODUCT,
            CatalogMigrationMapping.EntityType.VARIANT,
        ),
    ).exists()


@pytest.mark.django_db
def test_unconfirmed_album_price_is_reported_and_not_invented(tmp_path):
    """Релиз без подтверждённой цены остаётся без Product."""
    package = _prepare_package(tmp_path, 0)
    _, album, track = _create_content()
    path = package / BUNDLE_DIRECTORY / 'data' / 'releases.json'
    rows = _load(path)
    rows[0].update({
        'source_price': None,
        'target_price': '0.00',
        'price_status': 'MISSING_DEFAULTED_TO_ZERO',
        'price_requires_review': True,
        'price_policy': {
            'source_price': None,
            'target_price': '0.00',
            'price_status': 'MISSING_DEFAULTED_TO_ZERO',
            'requires_review': True,
        },
    })
    _write_json(path, rows)

    result = CatalogDigitalProductImporter(package).run()

    assert result.selected_albums == 0
    assert result.selected_tracks == 1
    assert result.skipped_unconfirmed_albums == ('release-00',)
    assert not Product.objects.filter(album=album).exists()
    assert Product.objects.filter(track=track, price=ZERO_MONEY).exists()


@pytest.mark.django_db
def test_dry_run_and_command_do_not_write(tmp_path):
    """Dry-run сообщает тот же план без Product и mappings."""
    package = _prepare_package(tmp_path, 0)
    _create_content()
    output = StringIO()

    call_command(
        'import_catalog_digital_products',
        package,
        dry_run=True,
        stdout=output,
    )

    assert 'DIGITAL PRODUCT IMPORT DRY-RUN' in output.getvalue()
    assert 'would_create=2' in output.getvalue()
    assert Product.objects.count() == 0
    assert ProductVariant.objects.count() == 0
    assert not CatalogMigrationMapping.objects.filter(
        entity_type__in=(
            CatalogMigrationMapping.EntityType.PRODUCT,
            CatalogMigrationMapping.EntityType.VARIANT,
        ),
    ).exists()


@pytest.mark.django_db
def test_v2_prices_tracks_namespace_and_repeat(tmp_path):
    """v2 пропускает review-цену и создаёт zero-price Track товары."""
    package = v2_package(tmp_path)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    config['artist_code_whitelist'] = [_code(0), _code(1)]
    _write_json(config_path, config)
    releases_path = bundle_root(package) / 'data' / 'releases.json'
    releases = _load(releases_path)
    for index, row in enumerate(releases):
        price = f'{100 + index}.00'
        row.update({
            'source_price': price,
            'target_price': price,
            'price_status': 'PRESERVED_ACCEPTED_PRICE',
            'price_requires_review': False,
            'price_policy': {
                'source_price': price,
                'target_price': price,
                'price_status': 'PRESERVED_ACCEPTED_PRICE',
                'requires_review': False,
            },
        })
    skipped_entity_id = releases[1]['entity_id']
    releases[1].update({
        'source_price': None,
        'target_price': None,
        'price_status': 'MISSING_PRICE_REVIEW',
        'price_requires_review': True,
        'price_policy': {
            'source_price': None,
            'target_price': None,
            'price_status': 'MISSING_PRICE_REVIEW',
            'requires_review': True,
        },
    })
    _write_json(releases_path, releases)
    CatalogProfileImporter(package).run()
    CatalogReleaseImporter(package).run()
    CatalogTrackImporter(package).run()

    result = CatalogDigitalProductImporter(package).run()

    assert result.selected_albums == 1
    assert result.selected_tracks == 2
    assert result.skipped_unconfirmed_albums == (skipped_entity_id,)
    assert (
        Product.objects.filter(
            product_type=Product.ProductType.TRACK,
            price=ZERO_MONEY,
        ).count()
        == 2
    )
    version = mapping_version(package)
    assert (
        CatalogMigrationMapping.objects.filter(
            bundle_version=version,
            entity_type=CatalogMigrationMapping.EntityType.PRODUCT,
        ).count()
        == 3
    )
    assert (
        CatalogMigrationMapping.objects.filter(
            bundle_version=version,
            entity_type=CatalogMigrationMapping.EntityType.VARIANT,
        ).count()
        == 3
    )

    repeated = CatalogDigitalProductImporter(package).run()

    assert repeated.already_mapped == 3
    assert repeated.created_products == 0
    assert Product.objects.count() == 3
    assert ProductVariant.objects.count() == 3
