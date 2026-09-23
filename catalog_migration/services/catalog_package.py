"""Prepare catalog package metadata for the one-shot import command."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any, Iterator

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings

from catalog_migration.services.catalog_bundle import V2_DIRECTORY

DEFAULT_S3_PACKAGE_PREFIX = 'migration-v2'
ROOT_METADATA = (
    'import_config.json',
    'artist_codes.json',
    'artist_slug_overrides.json',
)
EXTRA_METADATA = {
    'public_contacts': 'public_contacts.json',
    'telegram': 'telegram_bindings.json',
    'cdek': 'cdek_shipping_points.json',
}
BUNDLE_AUXILIARY_METADATA = (
    'reference/genres.json',
    'reference/merch_kinds.json',
)


class CatalogPackageError(RuntimeError):
    """Package metadata could not be prepared safely."""


class CatalogPackagePreparer:
    """Downloads only v2 metadata while leaving media objects in S3."""

    def __init__(
        self,
        *,
        s3_prefix: str = DEFAULT_S3_PACKAGE_PREFIX,
        s3_client: BaseClient | None = None,
    ):
        """Configure the private S3 prefix and optional test client."""
        self.s3_prefix = s3_prefix.strip('/')
        if not self.s3_prefix:
            raise CatalogPackageError('S3 prefix must not be empty')
        self._s3_client = s3_client

    @contextmanager
    def prepare(self, local_package_root: Path) -> Iterator[Path]:
        """Yield the local package or a temporary metadata-only S3 mirror."""
        if not settings.USE_S3_MEDIA:
            yield local_package_root
            return

        with TemporaryDirectory(prefix='catalog-migration-v2-') as directory:
            package_root = Path(directory)
            try:
                for relative in ROOT_METADATA:
                    self._download_json(relative, package_root)

                config = self._read_object(
                    package_root / 'import_config.json',
                    'import_config.json',
                )
                enabled = config.get('enabled')
                if not isinstance(enabled, dict):
                    raise CatalogPackageError(
                        'import_config.json: enabled must be an object',
                    )
                for stage, relative in EXTRA_METADATA.items():
                    if enabled.get(stage, False):
                        self._download_json(relative, package_root)

                bundle_relative = f'{V2_DIRECTORY}/bundle.json'
                self._download_json(bundle_relative, package_root)
                bundle = self._read_object(
                    package_root / bundle_relative,
                    bundle_relative,
                )
                metadata_paths = set(self._bundle_metadata_paths(bundle))
                metadata_paths.update(BUNDLE_AUXILIARY_METADATA)
                for relative in sorted(metadata_paths):
                    self._download_json(
                        f'{V2_DIRECTORY}/{relative}',
                        package_root,
                    )
            except (ClientError, OSError) as error:
                raise CatalogPackageError(
                    'Не удалось получить метаданные migration-v2 из S3',
                ) from error
            yield package_root

    def _download_json(self, relative: str, package_root: Path) -> None:
        path = self._safe_path(package_root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        response = self._get_s3_client().get_object(
            Bucket=settings.AWS_PRIVATE_STORAGE_BUCKET_NAME,
            Key=f'{self.s3_prefix}/{relative}',
        )
        body = response['Body']
        try:
            with path.open('wb') as target:
                while chunk := body.read(1024 * 1024):
                    target.write(chunk)
        finally:
            body.close()
        self._read_json(path, relative)

    @staticmethod
    def _bundle_metadata_paths(bundle: dict) -> tuple[str, ...]:
        paths: set[str] = set()
        for field in ('data', 'schema_files', 'media_manifests'):
            value = bundle.get(field)
            if not isinstance(value, dict):
                raise CatalogPackageError(
                    f'bundle.json: {field} must be an object',
                )
            paths.update(value.values())
        checksums = bundle.get('content_sha256')
        if not isinstance(checksums, dict):
            raise CatalogPackageError(
                'bundle.json: content_sha256 must be an object',
            )
        paths.update(checksums)
        if not all(isinstance(path, str) for path in paths):
            raise CatalogPackageError('bundle.json contains invalid paths')
        return tuple(sorted(paths))

    @staticmethod
    def _safe_path(package_root: Path, relative: str) -> Path:
        posix_path = PurePosixPath(relative)
        if (
            posix_path.is_absolute()
            or '..' in posix_path.parts
            or posix_path.suffix.lower() != '.json'
        ):
            raise CatalogPackageError(
                'Package contains an unsafe metadata path',
            )
        return package_root.joinpath(*posix_path.parts)

    @staticmethod
    def _read_json(path: Path, label: str) -> Any:
        try:
            return json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, json.JSONDecodeError) as error:
            raise CatalogPackageError(
                f'Некорректный JSON метаданных: {label}',
            ) from error

    @classmethod
    def _read_object(cls, path: Path, label: str) -> dict:
        value = cls._read_json(path, label)
        if not isinstance(value, dict):
            raise CatalogPackageError(
                f'Метаданные должны быть JSON object: {label}',
            )
        return value

    def _get_s3_client(self) -> BaseClient:
        if self._s3_client is None:
            for logger_name in ('boto3', 'botocore', 's3transfer'):
                logging.getLogger(logger_name).setLevel(logging.WARNING)
            self._s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                region_name=settings.AWS_S3_REGION_NAME,
                config=Config(
                    s3={
                        'addressing_style': settings.AWS_S3_ADDRESSING_STYLE,
                    },
                ),
            )
        return self._s3_client
