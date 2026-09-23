"""Тесты импорта изображений каталога migration-v1.3."""

import hashlib
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from PIL import Image as PillowImage
from django.core.management import call_command

from catalog_migration.services.catalog_bundle import (
    bundle_root,
    mapping_version,
)
from catalog_migration.services.catalog_image_import import (
    DEFAULT_SOURCE_PREFIX,
    CatalogImageImportError,
    CatalogImageImporter,
)
from catalog_migration.services.catalog_migration_preflight import (
    BUNDLE_DIRECTORY,
    BUNDLE_VERSION,
)
from catalog_migration.tests.test_catalog_migration_preflight import (
    _code,
    _load,
    _make_package,
    _write_json,
)
from catalog_migration.tests.test_catalog_release_import import (
    _create_profile_mapping,
)
from catalog_migration.tests.v2_package import v2_package

from store.models import (
    Album,
    AlbumArchive,
    CatalogMigrationMapping,
    Image,
    Merch,
)
from users.models import ArtistProfile


class FakeS3Client:
    """Read-only S3 fake с несколькими source objects."""

    def __init__(self, objects: dict[str, bytes]):
        """Сохраняет source objects и журнал чтений."""
        self.objects = objects
        self.gets: list[str] = []

    def get_object(self, **kwargs):
        key = kwargs['Key']
        self.gets.append(key)
        return {'Body': BytesIO(self.objects[key])}


def _png_bytes() -> bytes:
    output = BytesIO()
    PillowImage.new('RGB', (2, 2), color='red').save(output, format='PNG')
    return output.getvalue()


def _asset(
    asset_id: str,
    entity_type: str,
    entity_id: str,
    role: str,
    content: bytes,
) -> dict:
    bundle_path = f'media/images/{entity_type}/{asset_id}.png'
    return {
        'asset_id': asset_id,
        'bundle_path': bundle_path,
        'entity_id': entity_id,
        'entity_type': entity_type,
        'format': 'PNG',
        'height': 2,
        'mime': 'image/png',
        'normalization': 'NONE',
        'original_filename': f'{asset_id}.png',
        'role': role,
        'sha256': hashlib.sha256(content).hexdigest(),
        'size': len(content),
        'state': 'AVAILABLE',
        'width': 2,
    }


def _prepare_package(tmp_path: Path) -> tuple[Path, FakeS3Client]:
    package = _make_package(tmp_path)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    config['artist_code_whitelist'] = [_code(0)]
    _write_json(config_path, config)

    content = _png_bytes()
    assets = [
        _asset(
            'profile-image',
            'profile',
            'profile-00',
            'artist_cover',
            content,
        ),
        _asset(
            'release-image',
            'release',
            'release-00',
            'release_cover',
            content,
        ),
        _asset(
            'merch-image-1',
            'merch',
            'merch-00',
            'merch_image',
            content,
        ),
        _asset(
            'merch-image-2',
            'merch',
            'merch-00',
            'merch_image',
            content,
        ),
    ]
    lists = {
        'profiles': {'profile-00': ['profile-image']},
        'releases': {'release-00': ['release-image']},
        'merch': {'merch-00': ['merch-image-1', 'merch-image-2']},
    }
    for filename, selected in lists.items():
        path = package / BUNDLE_DIRECTORY / 'data' / f'{filename}.json'
        rows = _load(path)
        for row in rows:
            row['image_asset_ids'] = selected.get(row['entity_id'], [])
        _write_json(path, rows)
    _write_json(
        package / BUNDLE_DIRECTORY / 'media' / 'manifests' / 'images.json',
        {'assets': assets},
    )
    bundle_path = package / BUNDLE_DIRECTORY / 'bundle.json'
    bundle = _load(bundle_path)
    bundle['expected_counts']['images'] = len(assets)
    bundle['media_manifests'] = {'images': 'media/manifests/images.json'}
    _write_json(bundle_path, bundle)
    objects = {
        f'{DEFAULT_SOURCE_PREFIX}/{asset["bundle_path"]}': content
        for asset in assets
    }
    return package, FakeS3Client(objects)


def _create_targets(package: Path) -> tuple[ArtistProfile, Album, Merch]:
    artist = _create_profile_mapping(package, 0)
    album = Album.objects.bulk_create(
        [Album(artist=artist, name='Release 0')],
    )[0]
    CatalogMigrationMapping.objects.create(
        bundle_version=BUNDLE_VERSION,
        entity_type=CatalogMigrationMapping.EntityType.RELEASE,
        source_entity_id='release-00',
        django_pk=album.pk,
    )
    merch = Merch.objects.create(
        artist=artist,
        name='Merch 0',
        is_published=False,
    )
    CatalogMigrationMapping.objects.create(
        bundle_version=BUNDLE_VERSION,
        entity_type=CatalogMigrationMapping.EntityType.MERCH,
        source_entity_id='merch-00',
        django_pk=merch.pk,
    )
    return artist, album, merch


@pytest.fixture(autouse=True)
def _fake_bucket(settings: Any) -> None:
    settings.USE_S3_MEDIA = True
    settings.AWS_PRIVATE_STORAGE_BUCKET_NAME = 'fake-private'


@pytest.mark.django_db(transaction=True)
def test_import_saves_covers_and_ordered_merch_images_without_archive(
    tmp_path,
):
    """Первое фото Merch главное, а Album post_save не вызывается."""
    package, client = _prepare_package(tmp_path)
    artist, album, merch = _create_targets(package)

    with (
        patch.object(
            CatalogImageImporter,
            '_get_s3_client',
            return_value=client,
        ),
        patch(
            'store.services.album_archive.AlbumArchiveScheduler.schedule_by_id',
        ) as schedule_archive,
    ):
        result = CatalogImageImporter(package).run()

    artist.refresh_from_db()
    album.refresh_from_db()
    images = list(Image.objects.filter(merch=merch).order_by('pk'))
    assert result.created == {'profile': 1, 'release': 1, 'merch': 2}
    assert artist.cover.name.startswith('artists/covers/')
    assert album.cover_image.name.startswith('albums/covers/')
    assert [image.is_main for image in images] == [True, False]
    assert images[0].image.name.endswith('.png')
    assert images[1].image.name.endswith('.png')
    assert len(client.gets) == 4
    assert AlbumArchive.objects.count() == 0
    schedule_archive.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_local_import_reads_bundle_without_s3(tmp_path, settings):
    """Локальный режим читает image assets прямо из frozen bundle."""
    package, client = _prepare_package(tmp_path)
    artist, _, _ = _create_targets(package)
    settings.USE_S3_MEDIA = False
    manifest = _load(
        package / BUNDLE_DIRECTORY / 'media' / 'manifests' / 'images.json',
    )
    for asset in manifest['assets']:
        source_path = package / BUNDLE_DIRECTORY / asset['bundle_path']
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_key = f'{DEFAULT_SOURCE_PREFIX}/{asset["bundle_path"]}'
        source_path.write_bytes(client.objects[source_key])

    with patch.object(
        CatalogImageImporter,
        '_get_s3_client',
        side_effect=AssertionError('S3 must not be used'),
    ) as get_s3_client:
        result = CatalogImageImporter(package).run()

    artist.refresh_from_db()
    assert result.created == {'profile': 1, 'release': 1, 'merch': 2}
    assert artist.cover.storage.exists(artist.cover.name)
    assert client.gets == []
    get_s3_client.assert_not_called()


@pytest.mark.parametrize(
    ('changed_field', 'changed_value', 'error_pattern'),
    [
        (None, None, None),
        ('size', 1, 'Размер или SHA-256'),
        ('sha256', '0' * 64, 'Размер или SHA-256'),
        ('format', 'JPEG', 'Формат или размеры'),
    ],
)
def test_v2_mock_s3_key_and_content_validation(
    tmp_path,
    changed_field,
    changed_value,
    error_pattern,
):
    """v2 читает точный S3 key и проверяет size, SHA256 и формат."""
    package = v2_package(tmp_path)
    content = _png_bytes()
    asset = _asset(
        'v2-profile-image',
        'profile',
        'profile-00',
        'artist_cover',
        content,
    )
    asset['bundle_path'] = 'media/images/v2-profile-image.png'
    if changed_field is not None:
        asset[changed_field] = changed_value
    expected_key = (
        'migration-v2/zvuchno-migration-bundle-v2/'
        'media/images/v2-profile-image.png'
    )
    client = FakeS3Client({expected_key: content})
    importer = CatalogImageImporter(package)
    candidate = importer._candidate(asset)

    assert importer.bundle_root == bundle_root(package)
    assert importer.mapping_version == mapping_version(package)
    assert candidate.source_key == expected_key
    with patch.object(
        CatalogImageImporter,
        '_get_s3_client',
        return_value=client,
    ):
        if error_pattern is None:
            with importer._download(candidate) as downloaded:
                assert downloaded.read() == content
        else:
            with pytest.raises(CatalogImageImportError, match=error_pattern):
                importer._download(candidate)

    assert client.gets == [expected_key]


@pytest.mark.django_db
def test_dry_run_never_reads_s3_or_writes_images(tmp_path):
    """Dry-run ограничивается manifest и mappings."""
    package, client = _prepare_package(tmp_path)
    _create_targets(package)

    with patch.object(
        CatalogImageImporter,
        '_get_s3_client',
        return_value=client,
    ):
        result = CatalogImageImporter(package, dry_run=True).run()

    assert result.would_create == {'profile': 1, 'release': 1, 'merch': 2}
    assert client.gets == []
    assert Image.objects.count() == 0
    assert not ArtistProfile.objects.get().cover


@pytest.mark.django_db
def test_management_command_dry_run_reports_image_counts(tmp_path):
    """Management-команда использует тот же read-only план."""
    package, client = _prepare_package(tmp_path)
    _create_targets(package)
    output = StringIO()

    with patch.object(
        CatalogImageImporter,
        '_get_s3_client',
        return_value=client,
    ):
        call_command(
            'import_catalog_images',
            package,
            dry_run=True,
            stdout=output,
        )

    assert 'IMAGE IMPORT DRY-RUN' in output.getvalue()
    assert 'would_create profile=1 release=1 merch=2' in output.getvalue()
    assert client.gets == []


@pytest.mark.django_db(transaction=True)
def test_repeat_preserves_manually_replaced_images(tmp_path):
    """Любое существующее изображение защищает сущность от перезаписи."""
    package, client = _prepare_package(tmp_path)
    artist, album, merch = _create_targets(package)
    with patch.object(
        CatalogImageImporter,
        '_get_s3_client',
        return_value=client,
    ):
        CatalogImageImporter(package).run()
    ArtistProfile.objects.filter(pk=artist.pk).update(
        cover='manual/profile.png',
    )
    type(album).objects.filter(pk=album.pk).update(
        cover_image='manual/release.png',
    )
    Image.objects.filter(merch=merch, is_main=True).update(
        image='manual/merch.png',
    )
    reads_after_first_run = len(client.gets)

    with patch.object(
        CatalogImageImporter,
        '_get_s3_client',
        return_value=client,
    ):
        result = CatalogImageImporter(package).run()

    artist.refresh_from_db()
    album.refresh_from_db()
    assert result.created == {}
    assert result.existing == {'profile': 1, 'release': 1, 'merch': 2}
    assert artist.cover.name == 'manual/profile.png'
    assert album.cover_image.name == 'manual/release.png'
    assert Image.objects.get(merch=merch, is_main=True).image.name == (
        'manual/merch.png'
    )
    assert len(client.gets) == reads_after_first_run


@pytest.mark.django_db
def test_missing_mapping_blocks_all_s3_reads(tmp_path):
    """Недостающая сущность обнаруживается до первого source GET."""
    package, client = _prepare_package(tmp_path)
    artist = _create_profile_mapping(package, 0)
    merch = Merch.objects.create(artist=artist, name='Merch 0')
    CatalogMigrationMapping.objects.create(
        bundle_version=BUNDLE_VERSION,
        entity_type=CatalogMigrationMapping.EntityType.MERCH,
        source_entity_id='merch-00',
        django_pk=merch.pk,
    )

    with (
        patch.object(
            CatalogImageImporter,
            '_get_s3_client',
            return_value=client,
        ),
        pytest.raises(CatalogImageImportError, match='Mapping release'),
    ):
        CatalogImageImporter(package).run()

    assert client.gets == []
    assert not artist.cover
    assert Image.objects.count() == 0
