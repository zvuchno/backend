"""Focused offline tests of customer whitelist policy and version isolation."""

import pytest

from catalog_migration.services.catalog_bundle import (
    V2_DIRECTORY,
    bundle_root,
    mapping_version,
)
from catalog_migration.services.catalog_migration_preflight import (
    CatalogMigrationPreflight,
)
from catalog_migration.services.catalog_migration_registry import (
    CatalogMigrationRegistry,
)
from catalog_migration.tests.test_catalog_migration_preflight import (
    _load,
    _write_json,
)
from catalog_migration.tests.v2_package import v2_package


def test_v2_variable_roster_and_missing_audio_are_explicit(tmp_path):
    """V2 accepts its explicit roster and explicitly missing audio."""
    root = v2_package(tmp_path)
    result = CatalogMigrationPreflight(root).run()
    assert result.passed, result.render()
    assert bundle_root(root).name == V2_DIRECTORY


def test_v2_rejects_duplicate_track_positions(tmp_path):
    """V2 rejects duplicate positions within a release."""
    root = v2_package(tmp_path)
    path = bundle_root(root) / 'data/tracks.json'
    rows = _load(path)
    rows[1]['release_id'] = rows[0]['release_id']
    _write_json(path, rows)
    assert not CatalogMigrationPreflight(root).run().passed


@pytest.mark.django_db
def test_mapping_namespace_is_bundle_bound(tmp_path):
    """SHA256 bundle.json разделяет mappings разных сборок v2."""
    root = v2_package(tmp_path)
    old = mapping_version(root)
    registry = CatalogMigrationRegistry(root)
    registry.add_mapping('profile', 'profile-00', 123)
    path = bundle_root(root) / 'bundle.json'
    doc = _load(path)
    doc['source_revision'] = 'different'
    _write_json(path, doc)
    assert mapping_version(root) != old
    assert (
        CatalogMigrationRegistry(root).get_mapping(
            'profile',
            'profile-00',
        )
        is None
    )


def test_seven_images_have_no_count_cap(tmp_path):
    """A seven-image merch gallery is accepted without truncation."""
    root = v2_package(tmp_path)
    bundle = bundle_root(root)
    path = bundle / 'data/merch.json'
    items = _load(path)
    assets = []
    for n in range(7):
        aid = f'image-{n}'
        rel = f'media/images/{aid}.png'
        p = bundle / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'x')
        assets.append(
            dict(
                asset_id=aid,
                entity_id=items[0]['entity_id'],
                entity_type='merch',
                bundle_path=rel,
                sha256='0' * 64,
                size=1,
                format='PNG',
            ),
        )
    items[0]['image_asset_ids'] = [a['asset_id'] for a in assets]
    _write_json(path, items)
    _write_json(bundle / 'media/manifests/images.json', {'assets': assets})
    path = bundle / 'bundle.json'
    doc = _load(path)
    doc['expected_counts']['images'] = 7
    _write_json(path, doc)
    assert CatalogMigrationPreflight(root).run().passed


@pytest.mark.django_db
def test_v2_registry_connects_metadata_stages_and_preserves_positions(
    tmp_path,
):
    """Четыре metadata-этапа используют один DB namespace."""
    from catalog_migration.services.catalog_merch_import import (
        CatalogMerchImporter,
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

    from store.models import CatalogMigrationMapping, Track

    root = v2_package(tmp_path)
    bundle = bundle_root(root)
    merch_path = bundle / 'data/merch.json'
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
    variants_path = bundle / 'data/variants.json'
    variants = _load(variants_path)
    for index, row in enumerate(variants):
        row.update({
            'property_name': None,
            'property_value': 'simple',
            'target_stock': index + 1,
        })
    _write_json(variants_path, variants)
    _write_json(
        bundle / 'reference/merch_kinds.json',
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
    CatalogProfileImporter(root).run()
    CatalogReleaseImporter(root).run()
    CatalogTrackImporter(root).run()
    CatalogMerchImporter(root).run()
    version = mapping_version(root)
    assert (
        CatalogMigrationMapping.objects.filter(
            bundle_version=version,
            entity_type='track',
        ).count()
        == 3
    )
    assert not CatalogMigrationMapping.objects.filter(
        bundle_version='1.3',
    ).exists()
    for row in _load(bundle_root(root) / 'data/tracks.json'):
        pk = CatalogMigrationRegistry(root).get_mapping(
            'track',
            row['entity_id'],
        )
        track = Track.objects.get(pk=pk)
        assert track.position == row['position']
    before = Track.objects.count()
    CatalogTrackImporter(root).run()
    assert Track.objects.count() == before
    before_mappings = CatalogMigrationMapping.objects.count()
    CatalogMerchImporter(root).run()
    assert CatalogMigrationMapping.objects.count() == before_mappings
    assert CatalogMigrationRegistry(root).get_mappings('merch')
    assert CatalogMigrationRegistry(root).get_mappings('product')
    assert CatalogMigrationRegistry(root).get_mappings('variant')


def test_v2_media_importers_use_new_source_prefix_and_mapping_scope(tmp_path):
    """Media importers use the v2 source prefix and mapping namespace."""
    from catalog_migration.services.catalog_audio_import import (
        CatalogAudioImporter,
    )
    from catalog_migration.services.catalog_image_import import (
        CatalogImageImporter,
    )

    root = v2_package(tmp_path)
    for cls in [CatalogAudioImporter, CatalogImageImporter]:
        importer = cls(root)
        assert importer.bundle_root == bundle_root(root)
        assert importer.source_prefix.startswith('migration-v2')
        assert importer.mapping_version == mapping_version(root)


@pytest.mark.django_db
def test_v2_full_metadata_and_seven_local_images(
    tmp_path,
    settings,
    monkeypatch,
):
    """The metadata chain supports a seven-image local merch gallery."""
    import hashlib
    from io import BytesIO

    from PIL import Image as PILImage

    from catalog_migration.services.catalog_digital_product_import import (
        CatalogDigitalProductImporter,
    )
    from catalog_migration.services.catalog_image_import import (
        CatalogImageImporter,
    )
    from catalog_migration.services.catalog_merch_import import (
        CatalogMerchImporter,
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

    from store.models import Image, Product

    root = v2_package(tmp_path)
    bundle = bundle_root(root)
    _write_json(bundle / 'reference/merch_kinds.json', {'kinds': []})
    for dataset in ['merch', 'releases']:
        path = bundle / 'data' / f'{dataset}.json'
        rows = _load(path)
        for row in rows:
            if dataset == 'merch':
                row['release_id'] = None
            row.update(
                source_price='2800.00',
                target_price='2800.00',
                price_requires_review=False,
                price_status='PRESERVED_ACCEPTED_PRICE',
                price_policy={
                    'price_status': 'PRESERVED_ACCEPTED_PRICE',
                    'requires_review': False,
                },
            )
        _write_json(path, rows)
    path = bundle / 'data/variants.json'
    rows = _load(path)
    for row in rows:
        row['property_value'] = 'S-M'
    _write_json(path, rows)
    contents = BytesIO()
    PILImage.new('RGB', (2, 2)).save(contents, format='PNG')
    content = contents.getvalue()
    assets = []
    for n in range(7):
        aid = f'image-{n}'
        rel = f'media/images/{aid}.png'
        path = bundle / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        assets.append(
            dict(
                asset_id=aid,
                entity_id='merch-00',
                entity_type='merch',
                role='merch_image',
                bundle_path=rel,
                sha256=hashlib.sha256(content).hexdigest(),
                size=len(content),
                format='PNG',
                mime='image/png',
                width=2,
                height=2,
                state='AVAILABLE',
                normalization='NONE',
                original_filename='source.png',
            ),
        )
    _write_json(bundle / 'media/manifests/images.json', {'assets': assets})
    path = bundle / 'data/merch.json'
    rows = _load(path)
    rows[0]['image_asset_ids'] = [a['asset_id'] for a in assets]
    _write_json(path, rows)
    path = bundle / 'bundle.json'
    doc = _load(path)
    doc['expected_counts']['images'] = 7
    _write_json(path, doc)
    settings.USE_S3_MEDIA = False
    monkeypatch.setattr(
        CatalogImageImporter,
        '_get_s3_client',
        lambda _: pytest.fail('Unexpected S3 access'),
    )
    CatalogProfileImporter(root).run()
    CatalogReleaseImporter(root).run()
    CatalogTrackImporter(root).run()
    CatalogMerchImporter(root).run()
    CatalogDigitalProductImporter(root).run()
    CatalogImageImporter(root).run()
    assert Image.objects.count() == 7
    assert Image.objects.filter(is_main=True).count() == 1
    assert Product.objects.count() == 9
    CatalogMerchImporter(root).run()
    CatalogDigitalProductImporter(root).run()
    CatalogImageImporter(root).run()
    assert Image.objects.count() == 7 and Product.objects.count() == 9
