"""Synthetic v2 package used by importer regression tests."""

from catalog_migration.services.catalog_bundle import V2_DIRECTORY
from catalog_migration.services.catalog_migration_preflight import (
    BUNDLE_DIRECTORY,
)
from catalog_migration.tests.test_catalog_migration_preflight import (
    _load,
    _make_package,
    _write_json,
)


def v2_package(tmp_path):
    """Build a small self-contained v2 package below ``tmp_path``."""
    root = _make_package(tmp_path)
    (root / BUNDLE_DIRECTORY).rename(root / V2_DIRECTORY)
    bundle = root / V2_DIRECTORY
    for name in ['artist_codes.json', 'import_config.json']:
        path = root / name
        document = _load(path)
        document['bundle_version'] = '2.0'
        if name == 'import_config.json':
            for stage in ('telegram', 'cdek', 'public_contacts'):
                document['enabled'][stage] = False
        else:
            document['artists'] = document['artists'][:-1]
        _write_json(path, document)
    path = bundle / 'data/profiles.json'
    profiles = _load(path)[:-1]
    _write_json(path, profiles)
    codes = _load(root / 'artist_codes.json')['artists']
    path = root / 'import_config.json'
    document = _load(path)
    document['artist_code_whitelist'] = [row['code'] for row in codes]
    _write_json(path, document)
    path = root / 'artist_slug_overrides.json'
    document = _load(path)
    document['overrides'] = [
        row
        for row in document['overrides']
        if row['entity_id'] in {profile['entity_id'] for profile in profiles}
    ]
    _write_json(path, document)
    path = bundle / 'data/tracks.json'
    tracks = _load(path)
    for track in tracks:
        track.update(
            order_confirmed=True,
            audio_asset_id=None,
            audio_status='MISSING',
        )
    _write_json(path, tracks)
    for dataset in ('profiles', 'releases', 'merch'):
        path = bundle / 'data' / f'{dataset}.json'
        items = _load(path)
        for item in items:
            item['image_asset_ids'] = []
        _write_json(path, items)
    for kind in ('audio', 'images'):
        _write_json(
            bundle / 'media/manifests' / f'{kind}.json',
            {'assets': []},
        )
    path = bundle / 'bundle.json'
    document = _load(path)
    document['bundle_version'] = '2.0'
    document['expected_counts'].update(
        profiles=len(profiles),
        images=0,
        expected_audio_assets=0,
    )
    _write_json(path, document)
    return root
