"""Тесты DB-реестра разовой миграции каталога."""

from pathlib import Path

import pytest

from catalog_migration.services.catalog_bundle import (
    V2_DIRECTORY,
    mapping_version,
)
from catalog_migration.services.catalog_migration_preflight import (
    BUNDLE_DIRECTORY,
)
from catalog_migration.services.catalog_migration_registry import (
    CatalogMigrationRegistry,
    CatalogMigrationRegistryError,
)
from catalog_migration.tests.test_catalog_migration_preflight import (
    _load,
    _make_package,
    _write_json,
)

from store.models import CatalogMigrationMapping


@pytest.mark.django_db
def test_registry_reads_repeats_and_rejects_conflicts(tmp_path: Path) -> None:
    """Повтор безопасен, а source/target конфликты не исправляются."""
    package = _make_package(tmp_path)
    registry = CatalogMigrationRegistry(package)

    assert registry.add_mapping('profile', 'profile-00', 17) is True
    assert registry.add_mapping('profile', 'profile-00', 17) is False
    assert (
        CatalogMigrationRegistry(package).get_mapping(
            'profile',
            'profile-00',
        )
        == 17
    )
    assert CatalogMigrationMapping.objects.get().bundle_version == '1.3'

    with pytest.raises(
        CatalogMigrationRegistryError,
        match='другим Django PK',
    ):
        registry.add_mapping('profile', 'profile-00', 18)
    with pytest.raises(CatalogMigrationRegistryError, match='другой source'):
        registry.add_mapping('profile', 'profile-01', 17)

    assert CatalogMigrationMapping.objects.count() == 1


@pytest.mark.django_db
def test_add_mappings_is_atomic(tmp_path: Path) -> None:
    """Группа mappings сохраняется полностью либо не сохраняется вовсе."""
    package = _make_package(tmp_path)
    registry = CatalogMigrationRegistry(package)

    assert (
        registry.add_mappings({
            ('merch', 'merch-00'): 21,
            ('product', 'merch-00'): 22,
            ('variant', 'variant-00'): 23,
        })
        is True
    )
    assert registry.get_mappings('merch') == {'merch-00': 21}
    assert registry.get_mappings('product') == {'merch-00': 22}
    assert registry.get_mappings('variant') == {'variant-00': 23}
    before = CatalogMigrationMapping.objects.count()

    with pytest.raises(CatalogMigrationRegistryError, match='другой source'):
        registry.add_mappings({
            ('track', 'track-00'): 31,
            ('variant', 'variant-01'): 23,
        })

    assert CatalogMigrationMapping.objects.count() == before
    assert registry.get_mapping('track', 'track-00') is None


@pytest.mark.django_db
def test_v2_namespace_is_bound_to_bundle_sha256(tmp_path: Path) -> None:
    """Изменение bundle.json создаёт другой DB namespace."""
    package = _make_package(tmp_path)
    legacy_bundle = package / BUNDLE_DIRECTORY
    legacy_bundle.rename(package / V2_DIRECTORY)
    first = CatalogMigrationRegistry(package)
    first.add_mapping('profile', 'profile-00', 17)
    first_version = mapping_version(package)

    bundle_path = package / V2_DIRECTORY / 'bundle.json'
    bundle = _load(bundle_path)
    bundle['source_revision'] = 'another-frozen-source'
    _write_json(bundle_path, bundle)
    second = CatalogMigrationRegistry(package)

    assert second.mapping_version != first_version
    assert second.get_mapping('profile', 'profile-00') is None
    assert CatalogMigrationMapping.objects.filter(
        bundle_version=first_version,
        source_entity_id='profile-00',
        django_pk=17,
    ).exists()
