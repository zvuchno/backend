"""Тесты разового импорта Merch, Product и ProductVariant."""

from io import StringIO
from pathlib import Path
from typing import Never

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from catalog_migration.services.catalog_merch_import import (
    CatalogMerchImportError,
    CatalogMerchImporter,
)
from catalog_migration.services.catalog_migration_preflight import (
    BUNDLE_DIRECTORY,
)
from catalog_migration.services.catalog_migration_registry import (
    CatalogMigrationRegistry,
    CatalogMigrationRegistryError,
)
from catalog_migration.tests.test_catalog_migration_preflight import (
    _code,
    _load,
    _make_package,
    _write_json,
)

from store.models import (
    CatalogMigrationMapping,
    Image,
    Merch,
    MerchKind,
    Product,
    ProductVariant,
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

    merch_path = package / BUNDLE_DIRECTORY / 'data' / 'merch.json'
    merch_rows = _load(merch_path)
    for index, row in enumerate(merch_rows):
        row.update({
            'release_id': None,
            'description': f'Description {index}',
            'target_kind_slug': 'clothing',
            'target_price': f'{100 + index}.00',
            'property_name': None,
        })
    _write_json(merch_path, merch_rows)

    variants_path = package / BUNDLE_DIRECTORY / 'data' / 'variants.json'
    variant_rows = _load(variants_path)
    for index, row in enumerate(variant_rows):
        row.update({
            'property_name': None,
            'property_value': 'simple',
            'target_stock': index + 2,
        })
    _write_json(variants_path, variant_rows)
    _write_json(
        package / BUNDLE_DIRECTORY / 'reference' / 'merch_kinds.json',
        {
            'import_key': 'slug',
            'kinds': [
                {
                    'name': 'Одежда',
                    'slug': 'clothing',
                    'is_carrier': False,
                },
            ],
        },
    )
    return package


def _create_profile_mapping(package: Path, index: int) -> ArtistProfile:
    profile = ArtistProfile.objects.create(
        name=f'Profile {index}',
        slug=_code(index).lower(),
    )
    CatalogMigrationRegistry(package).add_mapping(
        'profile',
        f'profile-{index:02d}',
        profile.pk,
    )
    return profile


@pytest.mark.django_db
def test_first_import_creates_merch_product_variants_and_mappings(tmp_path):
    """Первый запуск создаёт связанный неопубликованный товар."""
    package = _prepare_package(tmp_path, 0)
    artist = _create_profile_mapping(package, 0)

    result = CatalogMerchImporter(package).run()

    assert result.created_merch == 1
    assert result.created_products == 1
    assert result.created_variants == 1
    merch = Merch.objects.get()
    product = Product.objects.get()
    variant = ProductVariant.objects.get()
    assert merch.artist == artist
    assert merch.name == 'Merch 0'
    assert merch.description == 'Description 0'
    assert merch.kind.slug == 'clothing'
    assert merch.created_by_id is None
    assert merch.payout_recipient_id is None
    assert merch.is_active is True
    assert merch.is_published is False
    assert product.merch == merch
    assert product.product_type == Product.ProductType.MERCH
    assert str(product.price) == '100.0000'
    assert product.property_name == ''
    assert variant.product == product
    assert variant.property_value == 'simple'
    assert variant.stock == 2
    assert variant.sku.startswith(f'MER-{artist.pk}-')
    assert variant.is_active is True
    assert MerchKind.objects.count() == 1
    assert Image.objects.count() == 0
    assert get_user_model().objects.count() == 0
    registry = CatalogMigrationRegistry(package)
    assert registry.get_mappings('merch') == {'merch-00': merch.pk}
    assert registry.get_mappings('product') == {'merch-00': product.pk}
    assert registry.get_mappings('variant') == {'variant-00': variant.pk}
    assert CatalogMigrationMapping.objects.count() == 4


@pytest.mark.django_db
def test_repeated_import_preserves_mapped_human_changes(tmp_path):
    """Повторный запуск не создаёт дубли и не обновляет товар."""
    package = _prepare_package(tmp_path, 0)
    _create_profile_mapping(package, 0)
    CatalogMerchImporter(package).run()
    merch = Merch.objects.get()
    product = Product.objects.get()
    variant = ProductVariant.objects.get()
    merch.name = 'Изменено человеком'
    merch.save(update_fields=('name',))
    product.price = 777
    product.save(update_fields=('price',))
    variant.stock = 99
    variant.save(update_fields=('stock',))

    result = CatalogMerchImporter(package).run()

    merch.refresh_from_db()
    product.refresh_from_db()
    variant.refresh_from_db()
    assert result.created_merch == 0
    assert result.created_products == 0
    assert result.created_variants == 0
    assert result.already_mapped == 1
    assert Merch.objects.count() == 1
    assert Product.objects.count() == 1
    assert ProductVariant.objects.count() == 1
    assert merch.name == 'Изменено человеком'
    assert product.price == 777
    assert variant.stock == 99


@pytest.mark.django_db
def test_dry_run_validates_without_writes(tmp_path):
    """Dry-run показывает план, не создавая товар и справочник."""
    package = _prepare_package(tmp_path, 0)
    _create_profile_mapping(package, 0)
    mappings_before = CatalogMigrationMapping.objects.count()

    result = CatalogMerchImporter(package, dry_run=True).run()

    assert result.would_create_merch == 1
    assert result.would_create_products == 1
    assert result.would_create_variants == 1
    assert Merch.objects.count() == 0
    assert Product.objects.count() == 0
    assert ProductVariant.objects.count() == 0
    assert MerchKind.objects.count() == 0
    assert CatalogMigrationMapping.objects.count() == mappings_before


@pytest.mark.django_db
def test_management_command_dry_run_reports_plan(tmp_path):
    """Management-команда вызывает тот же read-only dry-run."""
    package = _prepare_package(tmp_path, 0)
    _create_profile_mapping(package, 0)
    output = StringIO()

    call_command('import_catalog_merch', package, dry_run=True, stdout=output)

    assert 'MERCH IMPORT DRY-RUN' in output.getvalue()
    assert 'would_create_merch=1' in output.getvalue()
    assert Merch.objects.count() == 0
    assert Product.objects.count() == 0
    assert ProductVariant.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_registry_write_failure_rolls_back_whole_merch(
    tmp_path,
    monkeypatch,
):
    """Ошибка DB mapping откатывает товар целиком."""
    package = _prepare_package(tmp_path, 0)
    _create_profile_mapping(package, 0)

    def fail_mappings(*args, **kwargs) -> Never:
        raise CatalogMigrationRegistryError('test registry failure')

    monkeypatch.setattr(
        CatalogMigrationRegistry,
        'add_mappings',
        fail_mappings,
    )

    with pytest.raises(
        CatalogMerchImportError,
        match='Не удалось записать mappings.*entity_id=merch-00',
    ):
        CatalogMerchImporter(package).run()

    assert Merch.objects.count() == 0
    assert Product.objects.count() == 0
    assert ProductVariant.objects.count() == 0
    assert MerchKind.objects.count() == 0
    assert CatalogMigrationMapping.objects.count() == 1
    registry = CatalogMigrationRegistry(package)
    assert registry.get_mappings('merch') == {}
    assert registry.get_mappings('product') == {}
    assert registry.get_mappings('variant') == {}


@pytest.mark.django_db
def test_incomplete_registry_mappings_block_import(tmp_path):
    """Частичный набор mappings не дополняется автоматически."""
    package = _prepare_package(tmp_path, 0)
    _create_profile_mapping(package, 0)
    CatalogMigrationRegistry(package).add_mapping(
        'merch',
        'merch-00',
        9001,
    )

    with pytest.raises(CatalogMerchImportError, match='Неполный набор'):
        CatalogMerchImporter(package).run()

    assert Merch.objects.count() == 0
    assert Product.objects.count() == 0
    assert ProductVariant.objects.count() == 0


@pytest.mark.django_db
def test_registry_mappings_to_missing_objects_block_import(tmp_path):
    """Полный DB-набор с отсутствующими объектами блокирует повтор."""
    package = _prepare_package(tmp_path, 0)
    _create_profile_mapping(package, 0)
    CatalogMigrationRegistry(package).add_mappings({
        ('merch', 'merch-00'): 9001,
        ('product', 'merch-00'): 9002,
        ('variant', 'variant-00'): 9003,
    })

    with pytest.raises(
        CatalogMerchImportError,
        match='указывает на удалённый объект',
    ):
        CatalogMerchImporter(package).run()

    assert Merch.objects.count() == 0
    assert Product.objects.count() == 0
    assert ProductVariant.objects.count() == 0


@pytest.mark.django_db
def test_registry_mappings_with_wrong_relations_are_rejected(tmp_path):
    """Связи Product с mapped Merch проверяются при повторе."""
    package = _prepare_package(tmp_path, 0)
    artist = _create_profile_mapping(package, 0)
    CatalogMerchImporter(package).run()
    other_merch = Merch.objects.bulk_create([
        Merch(artist=artist, name='Other merch'),
    ])[0]
    Product.objects.update(merch=other_merch)

    with pytest.raises(
        CatalogMerchImportError,
        match='Mappings товара конфликтуют',
    ):
        CatalogMerchImporter(package).run()

    assert Merch.objects.count() == 2
    assert Product.objects.count() == 1
    assert ProductVariant.objects.count() == 1
