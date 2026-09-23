"""Focused tests for metadata-only catalog package preparation."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from catalog_migration.services.catalog_bundle import V2_DIRECTORY
from catalog_migration.services.catalog_migration_preflight import (
    CatalogMigrationPreflight,
)
from catalog_migration.services.catalog_package import (
    CatalogPackageError,
    CatalogPackagePreparer,
)
from catalog_migration.tests.test_catalog_migration_preflight import (
    _load,
    _write_json,
)
from catalog_migration.tests.v2_package import v2_package


class FakeS3Client:
    """Return in-memory objects and record requested keys."""

    def __init__(self, objects: dict[str, bytes]):
        """Store objects available to get_object()."""
        self.objects = objects
        self.gets: list[str] = []

    def get_object(self, **kwargs):  # noqa: ANN201
        key = kwargs['Key']
        self.gets.append(key)
        try:
            content = self.objects[key]
        except KeyError as error:
            raise ClientError(
                {'Error': {'Code': 'NoSuchKey', 'Message': 'missing'}},
                'GetObject',
            ) from error
        return {'Body': io.BytesIO(content)}


def _metadata_objects(package: Path) -> dict[str, bytes]:
    return {
        (
            f'migration-v2/{path.relative_to(package).as_posix()}'
        ): path.read_bytes()
        for path in package.rglob('*.json')
    }


def _s3_v2_package(tmp_path: Path) -> Path:
    package = v2_package(tmp_path)
    reference_root = package / V2_DIRECTORY / 'reference'
    reference_root.mkdir(parents=True, exist_ok=True)
    for filename in ('genres.json', 'merch_kinds.json'):
        _write_json(reference_root / filename, {})
    bundle_path = package / V2_DIRECTORY / 'bundle.json'
    bundle = _load(bundle_path)
    bundle['media_manifests'] = {
        'audio': 'media/manifests/audio.json',
        'images': 'media/manifests/images.json',
    }
    bundle['content_sha256'] = {}
    _write_json(bundle_path, bundle)
    return package


def test_s3_preparation_downloads_metadata_but_not_media(tmp_path, settings):
    """Mirror only metadata and delete the temporary package afterwards."""
    source = _s3_v2_package(tmp_path / 'source')
    objects = _metadata_objects(source)
    objects[
        f'migration-v2/{V2_DIRECTORY}/media/audio/originals/source.wav'
    ] = b'not requested'
    client = FakeS3Client(objects)
    settings.USE_S3_MEDIA = True
    prepared_path = None

    with CatalogPackagePreparer(s3_client=client).prepare(
        tmp_path / 'absent-local-package',
    ) as package:
        prepared_path = package
        assert CatalogMigrationPreflight(package).run().passed
        assert (package / 'import_config.json').is_file()
        assert (package / V2_DIRECTORY / 'bundle.json').is_file()
        assert not any(
            (package / V2_DIRECTORY / 'media').rglob('*.wav'),
        )

    assert prepared_path is not None
    assert not prepared_path.exists()
    assert all('/media/audio/originals/' not in key for key in client.gets)
    assert all('/media/images/' not in key for key in client.gets)


def test_local_preparation_keeps_existing_package(tmp_path, settings):
    """Leave the existing local package untouched when S3 media is off."""
    settings.USE_S3_MEDIA = False
    package = tmp_path / 'local-package'
    package.mkdir()
    client = FakeS3Client({})

    with CatalogPackagePreparer(s3_client=client).prepare(package) as prepared:
        assert prepared == package

    assert package.is_dir()
    assert client.gets == []


@pytest.mark.parametrize(
    ('relative', 'content'),
    [
        ('import_config.json', b'{broken'),
        ('artist_codes.json', None),
    ],
)
def test_missing_or_corrupt_metadata_stops_preparation(
    tmp_path,
    settings,
    relative,
    content,
):
    """Reject missing or malformed metadata before yielding a package."""
    source = _s3_v2_package(tmp_path / 'source')
    objects = _metadata_objects(source)
    key = f'migration-v2/{relative}'
    if content is None:
        objects.pop(key)
    else:
        objects[key] = content
    settings.USE_S3_MEDIA = True

    with pytest.raises(CatalogPackageError):
        with CatalogPackagePreparer(s3_client=FakeS3Client(objects)).prepare(
            tmp_path / 'absent-local-package',
        ):
            raise AssertionError('invalid package must not be yielded')
