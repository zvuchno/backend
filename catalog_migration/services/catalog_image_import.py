"""Простой create-only импорт изображений каталога bundle v1.3."""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import SpooledTemporaryFile
from typing import Any, BinaryIO, Callable

import boto3
from PIL import Image as PillowImage
from PIL import UnidentifiedImageError
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import IntegrityError, transaction

from catalog_migration.services.catalog_bundle import (
    bundle_root,
    bundle_version,
    mapping_version,
)
from catalog_migration.services.catalog_migration_preflight import (
    CatalogMigrationPreflight,
    PreflightResult,
)

from store.models import Album, CatalogMigrationMapping, Image, Merch
from store.services.merch_image import MerchImageService
from users.models import ArtistProfile

DEFAULT_SOURCE_PREFIX = 'migration/v1.3/zvuchno-migration-bundle-v1.3'
MAX_IMAGE_BYTES = 10 * 1024 * 1024
JsonObject = dict[str, Any]


class CatalogImageImportError(RuntimeError):
    """Безопасная ошибка, блокирующая импорт изображений."""


@dataclass(frozen=True)
class ImageCandidate:
    """Однозначная связь manifest asset с bundle entity."""

    asset: JsonObject
    entity_type: str
    entity_id: str
    source_key: str


@dataclass(frozen=True)
class CatalogImageImportResult:
    """Счётчики изображений по типам сущностей."""

    preflight: PreflightResult
    selected: dict[str, int]
    created: dict[str, int]
    existing: dict[str, int]
    would_create: dict[str, int]
    dry_run: bool

    def render(self) -> str:
        """Формирует обезличенный итог management-команды."""
        mode = 'DRY-RUN' if self.dry_run else 'PASS'

        def counters(values: dict[str, int]) -> str:
            return ' '.join(
                f'{kind}={values.get(kind, 0)}'
                for kind in ('profile', 'release', 'merch')
            )

        return '\n'.join((
            f'IMAGE IMPORT {mode}',
            f'selected {counters(self.selected)}',
            f'created {counters(self.created)}',
            f'existing {counters(self.existing)}',
            f'would_create {counters(self.would_create)}',
            'publication=unchanged users=unchanged products=unchanged tasks=0',
        ))


class CatalogImageImporter:
    """Подключает выбранные оригиналы к ранее импортированным объектам."""

    role_by_type = {
        'profile': 'artist_cover',
        'release': 'release_cover',
        'merch': 'merch_image',
    }
    mapping_type_by_entity = {
        'profile': CatalogMigrationMapping.EntityType.PROFILE,
        'release': CatalogMigrationMapping.EntityType.RELEASE,
        'merch': CatalogMigrationMapping.EntityType.MERCH,
    }

    def __init__(
        self,
        package_root: Path | str,
        *,
        dry_run: bool = False,
        asset_id: str | None = None,
        source_prefix: str = DEFAULT_SOURCE_PREFIX,
        progress_callback: Callable[[int, int], None] | None = None,
    ):
        """Сохраняет путь, фильтр и неизменяемый S3 source prefix."""
        self.package_root = Path(package_root).expanduser()
        self.bundle_version = bundle_version(self.package_root)
        self.mapping_version = mapping_version(self.package_root)
        self.bundle_root = bundle_root(self.package_root)
        self.dry_run = dry_run
        self.asset_id = asset_id
        self.source_prefix = source_prefix.strip('/')
        if (
            self.bundle_version == '2.0'
            and source_prefix == DEFAULT_SOURCE_PREFIX
        ):
            self.source_prefix = 'migration-v2/' + self.bundle_root.name
        self.progress_callback = progress_callback
        self.data_by_type: dict[str, dict[str, JsonObject]] = {}
        self.assets_by_entity: dict[tuple[str, str], list[JsonObject]] = {}
        self._s3_client: BaseClient | None = None

    def run(self) -> CatalogImageImportResult:
        """Выполняет preflight, проверки mappings и импорт."""
        preflight = CatalogMigrationPreflight(self.package_root).run()
        if not preflight.passed:
            raise CatalogImageImportError(preflight.render())

        config = self._read_object(self.package_root / 'import_config.json')
        candidates = self._load_candidates(config)
        targets = self._validate_mappings(candidates)
        existing = self._classify_existing(candidates, targets)
        selected_counts = self._count(candidates)
        existing_counts = self._count(
            candidate
            for candidate in candidates
            if (candidate.entity_type, candidate.entity_id) in existing
        )
        pending = [
            candidate
            for candidate in candidates
            if (candidate.entity_type, candidate.entity_id) not in existing
        ]
        pending_counts = self._count(pending)
        total = len(candidates)
        processed = total - len(pending)
        self._report_progress(processed, total)
        if self.dry_run:
            return CatalogImageImportResult(
                preflight=preflight,
                selected=selected_counts,
                created={},
                existing=existing_counts,
                would_create=pending_counts,
                dry_run=True,
            )

        created = defaultdict(int)
        singles = [
            candidate
            for candidate in pending
            if candidate.entity_type in {'profile', 'release'}
        ]
        for candidate in singles:
            if self._import_single(candidate):
                created[candidate.entity_type] += 1
            processed += 1
            self._report_progress(processed, total)

        merch_groups: dict[str, list[ImageCandidate]] = defaultdict(list)
        for candidate in pending:
            if candidate.entity_type == 'merch':
                merch_groups[candidate.entity_id].append(candidate)
        for entity_id in sorted(merch_groups):
            imported = self._import_merch_group(
                entity_id,
                merch_groups[entity_id],
            )
            created['merch'] += imported
            processed += len(merch_groups[entity_id])
            self._report_progress(processed, total)

        return CatalogImageImportResult(
            preflight=preflight,
            selected=selected_counts,
            created=dict(created),
            existing=existing_counts,
            would_create={},
            dry_run=False,
        )

    def _report_progress(self, processed: int, total: int) -> None:
        if self.progress_callback is not None:
            self.progress_callback(processed, total)

    def _load_candidates(self, config: JsonObject) -> list[ImageCandidate]:
        manifest = self._read_object(
            self.bundle_root / 'media' / 'manifests' / 'images.json',
        )
        assets = manifest.get('assets')
        if not isinstance(assets, list) or not all(
            isinstance(row, dict) for row in assets
        ):
            raise CatalogImageImportError(
                'images.json: ожидается массив assets',
            )
        self._validate_manifest(assets)

        codes = self._read_object(self.package_root / 'artist_codes.json')
        whitelist = set(config['artist_code_whitelist'])
        profile_ids = {
            row['entity_id']
            for row in codes['artists']
            if row['code'] in whitelist
        }
        enabled = config['enabled']
        selected_entities = {
            'profile': (profile_ids if enabled['profiles'] else set()),
            'release': {
                entity_id
                for entity_id, row in self.data_by_type['release'].items()
                if enabled['releases'] and row['profile_id'] in profile_ids
            },
            'merch': {
                entity_id
                for entity_id, row in self.data_by_type['merch'].items()
                if enabled['merch'] and row['profile_id'] in profile_ids
            },
        }
        candidates = []
        for entity_type in ('profile', 'release', 'merch'):
            for entity_id in sorted(selected_entities[entity_type]):
                for asset in self.assets_by_entity.get(
                    (entity_type, entity_id),
                    (),
                ):
                    candidates.append(self._candidate(asset))

        if self.asset_id is not None:
            matching = [
                candidate
                for candidate in candidates
                if candidate.asset['asset_id'] == self.asset_id
            ]
            if not matching:
                raise CatalogImageImportError(
                    'Изображение не входит в выбранный whitelist; '
                    f'asset_id={self.asset_id}',
                )
            candidate = matching[0]
            if (
                candidate.entity_type == 'merch'
                and len(
                    self.assets_by_entity[
                        (candidate.entity_type, candidate.entity_id)
                    ],
                )
                != 1
            ):
                raise CatalogImageImportError(
                    'Точечный импорт Merch допустим только для товара с '
                    'одним изображением; порядок нельзя импортировать '
                    'частично',
                )
            candidates = matching
        return candidates

    def _validate_manifest(  # noqa: C901
        self,
        assets: list[JsonObject],
    ) -> None:
        datasets = {
            'profile': self._read_array(
                self.bundle_root / 'data' / 'profiles.json',
            ),
            'release': self._read_array(
                self.bundle_root / 'data' / 'releases.json',
            ),
            'merch': self._read_array(
                self.bundle_root / 'data' / 'merch.json',
            ),
        }
        self.data_by_type = {
            kind: {row['entity_id']: row for row in rows}
            for kind, rows in datasets.items()
        }
        by_entity: dict[tuple[str, str], list[JsonObject]] = defaultdict(list)
        asset_ids = set()
        paths = set()
        errors = []
        for asset in assets:
            asset_id = asset.get('asset_id')
            entity_type = asset.get('entity_type')
            entity_id = asset.get('entity_id')
            bundle_path = asset.get('bundle_path')
            if not isinstance(asset_id, str) or not asset_id:
                errors.append('images.json: некорректный asset_id')
                continue
            if asset_id in asset_ids:
                errors.append(
                    f'images.json: повторяющийся asset_id={asset_id}',
                )
            asset_ids.add(asset_id)
            if entity_type not in self.role_by_type:
                errors.append(
                    f'images.json: неизвестный тип; asset_id={asset_id}',
                )
                continue
            if (
                not isinstance(entity_id, str)
                or entity_id not in self.data_by_type[entity_type]
            ):
                errors.append(
                    f'images.json: битая ссылка; asset_id={asset_id}',
                )
                continue
            if asset.get('role') != self.role_by_type[entity_type]:
                errors.append(
                    f'images.json: неверная роль; asset_id={asset_id}',
                )
            if not self._valid_asset_fields(asset):
                errors.append(
                    f'images.json: неверные поля; asset_id={asset_id}',
                )
            if isinstance(bundle_path, str) and bundle_path in paths:
                errors.append(
                    f'images.json: повторяющийся путь; asset_id={asset_id}',
                )
            if isinstance(bundle_path, str):
                paths.add(bundle_path)
            by_entity[(entity_type, entity_id)].append(asset)

        for entity_type, rows in self.data_by_type.items():
            for entity_id, row in rows.items():
                expected = row.get('image_asset_ids')
                actual = [
                    asset['asset_id']
                    for asset in by_entity.get((entity_type, entity_id), ())
                ]
                if not isinstance(expected, list) or expected != actual:
                    errors.append(
                        'images.json: порядок не совпадает; '
                        f'entity_id={entity_id}',
                    )
        bundle = self._read_object(self.bundle_root / 'bundle.json')
        expected_count = bundle.get('expected_counts', {}).get('images')
        if expected_count != len(assets):
            errors.append('images.json: количество не совпадает с bundle.json')
        if errors:
            raise CatalogImageImportError('\n'.join(sorted(set(errors))))
        self.assets_by_entity = dict(by_entity)

    @staticmethod
    def _valid_asset_fields(asset: JsonObject) -> bool:
        bundle_path = asset.get('bundle_path')
        if not isinstance(bundle_path, str):
            return False
        path = PurePosixPath(bundle_path)
        if path.is_absolute() or '..' in path.parts:
            return False
        digest = asset.get('sha256')
        size = asset.get('size')
        dimensions = (asset.get('width'), asset.get('height'))
        return (
            path.parts[:2] == ('media', 'images')
            and isinstance(digest, str)
            and len(digest) == 64
            and all(char in '0123456789abcdefABCDEF' for char in digest)
            and isinstance(size, int)
            and not isinstance(size, bool)
            and 0 < size <= MAX_IMAGE_BYTES
            and all(
                isinstance(value, int)
                and not isinstance(value, bool)
                and value > 0
                for value in dimensions
            )
            and asset.get('format') in {'JPEG', 'PNG', 'WEBP'}
            and asset.get('mime')
            in {
                'image/jpeg',
                'image/png',
                'image/webp',
            }
            and asset.get('state') == 'AVAILABLE'
            and asset.get('normalization')
            in {'NONE', 'JPEG_RECOMPRESSED', 'JPEG_RESIZED'}
            and isinstance(asset.get('original_filename'), str)
            and bool(asset.get('original_filename'))
        )

    def _candidate(self, asset: JsonObject) -> ImageCandidate:
        return ImageCandidate(
            asset=asset,
            entity_type=asset['entity_type'],
            entity_id=asset['entity_id'],
            source_key=(
                f'{self.source_prefix}/{asset["bundle_path"].lstrip("/")}'
            ),
        )

    def _validate_mappings(
        self,
        candidates: list[ImageCandidate],
    ) -> dict[tuple[str, str], ArtistProfile | Album | Merch]:
        entity_ids = {
            kind: {
                candidate.entity_id
                for candidate in candidates
                if candidate.entity_type == kind
            }
            for kind in self.role_by_type
        }
        targets: dict[tuple[str, str], ArtistProfile | Album | Merch] = {}
        errors = []
        model_by_type = {
            'profile': ArtistProfile,
            'release': Album,
            'merch': Merch,
        }
        for entity_type, ids in entity_ids.items():
            mappings = {
                row.source_entity_id: row
                for row in CatalogMigrationMapping.objects.filter(
                    bundle_version=self.mapping_version,
                    entity_type=self.mapping_type_by_entity[entity_type],
                    source_entity_id__in=ids,
                )
            }
            objects = model_by_type[entity_type].objects.in_bulk(
                mapping.django_pk for mapping in mappings.values()
            )
            for entity_id in ids:
                mapping = mappings.get(entity_id)
                if mapping is None:
                    errors.append(
                        f'Mapping {entity_type} отсутствует; '
                        f'entity_id={entity_id}',
                    )
                elif mapping.django_pk not in objects:
                    errors.append(
                        f'Mapping {entity_type} осиротел; '
                        f'entity_id={entity_id}',
                    )
                else:
                    targets[(entity_type, entity_id)] = objects[
                        mapping.django_pk
                    ]

        self._validate_target_artists(targets, errors)
        if errors:
            raise CatalogImageImportError('\n'.join(sorted(errors)))
        return targets

    def _validate_target_artists(
        self,
        targets: dict[tuple[str, str], ArtistProfile | Album | Merch],
        errors: list[str],
    ) -> None:
        profile_ids = {
            self.data_by_type[kind][entity_id]['profile_id']
            for kind, entity_id in targets
            if kind in {'release', 'merch'}
        }
        profile_mappings = {
            row.source_entity_id: row
            for row in CatalogMigrationMapping.objects.filter(
                bundle_version=self.mapping_version,
                entity_type=CatalogMigrationMapping.EntityType.PROFILE,
                source_entity_id__in=profile_ids,
            )
        }
        for (kind, entity_id), target in targets.items():
            if kind not in {'release', 'merch'}:
                continue
            profile_id = self.data_by_type[kind][entity_id]['profile_id']
            profile_mapping = profile_mappings.get(profile_id)
            if profile_mapping is None:
                errors.append(
                    'Mapping ArtistProfile отсутствует; '
                    f'entity_id={entity_id}',
                )
            elif target.artist_id != profile_mapping.django_pk:
                errors.append(
                    f'Mapping {kind} конфликтует с профилем; '
                    f'entity_id={entity_id}',
                )

    @staticmethod
    def _classify_existing(
        candidates: list[ImageCandidate],
        targets: dict[tuple[str, str], ArtistProfile | Album | Merch],
    ) -> set[tuple[str, str]]:
        existing = set()
        for candidate in candidates:
            key = (candidate.entity_type, candidate.entity_id)
            target = targets[key]
            if candidate.entity_type == 'profile' and target.cover:
                existing.add(key)
            elif candidate.entity_type == 'release' and target.cover_image:
                existing.add(key)
            elif (
                candidate.entity_type == 'merch'
                and Image.objects.filter(
                    merch_id=target.pk,
                ).exists()
            ):
                existing.add(key)
        return existing

    def _import_single(self, candidate: ImageCandidate) -> bool:
        model = ArtistProfile if candidate.entity_type == 'profile' else Album
        field_name = (
            'cover' if candidate.entity_type == 'profile' else 'cover_image'
        )
        mapping_type = self.mapping_type_by_entity[candidate.entity_type]
        try:
            with transaction.atomic():
                mapping = (
                    CatalogMigrationMapping.objects.select_for_update().get(
                        bundle_version=self.mapping_version,
                        entity_type=mapping_type,
                        source_entity_id=candidate.entity_id,
                    )
                )
                target = model.objects.select_for_update().get(
                    pk=mapping.django_pk,
                )
                if getattr(target, field_name):
                    return False
                temporary = self._download(candidate)
                field = getattr(target, field_name)
                saved_name = ''
                try:
                    with temporary:
                        field.save(
                            candidate.asset['original_filename'],
                            File(temporary),
                            save=False,
                        )
                    saved_name = field.name
                    # QuerySet.update намеренно обходит Album post_save,
                    # поэтому импорт cover не запускает AlbumArchive.
                    model.objects.filter(pk=target.pk).update(
                        **{field_name: saved_name},
                    )
                except (ClientError, IntegrityError, OSError):
                    if saved_name:
                        field.storage.delete(saved_name)
                    raise
                return True
        except (ClientError, OSError, UnidentifiedImageError) as error:
            raise CatalogImageImportError(
                'Не удалось сохранить изображение; '
                f'entity_id={candidate.entity_id}',
            ) from error
        except (
            CatalogMigrationMapping.DoesNotExist,
            model.DoesNotExist,
        ) as error:
            raise CatalogImageImportError(
                f'Mapping осиротел; entity_id={candidate.entity_id}',
            ) from error

    def _import_merch_group(
        self,
        entity_id: str,
        candidates: list[ImageCandidate],
    ) -> int:
        candidates_by_id = {
            candidate.asset['asset_id']: candidate for candidate in candidates
        }
        ordered_ids = self.data_by_type['merch'][entity_id]['image_asset_ids']
        ordered = [candidates_by_id[asset_id] for asset_id in ordered_ids]
        saved_files: list[tuple[Any, str]] = []
        try:
            with transaction.atomic():
                mapping = (
                    CatalogMigrationMapping.objects.select_for_update().get(
                        bundle_version=self.mapping_version,
                        entity_type=CatalogMigrationMapping.EntityType.MERCH,
                        source_entity_id=entity_id,
                    )
                )
                merch = Merch.objects.select_for_update().get(
                    pk=mapping.django_pk,
                )
                if Image.objects.filter(merch=merch).exists():
                    return 0
                for index, candidate in enumerate(ordered):
                    temporary = self._download(candidate)
                    with temporary:
                        image = MerchImageService.create_image(
                            merch=merch,
                            validated_data={
                                'image': File(
                                    temporary,
                                    name=candidate.asset['original_filename'],
                                ),
                                'is_main': index == 0,
                            },
                        )
                    saved_files.append((image.image.storage, image.image.name))
                return len(ordered)
        except (
            ClientError,
            IntegrityError,
            OSError,
            UnidentifiedImageError,
            ValidationError,
        ) as error:
            for storage, name in saved_files:
                try:
                    storage.delete(name)
                except (ClientError, OSError):
                    pass
            raise CatalogImageImportError(
                'Не удалось сохранить изображения Merch; '
                f'entity_id={entity_id}',
            ) from error
        except CatalogImageImportError:
            self._delete_saved_files(saved_files)
            raise
        except (
            CatalogMigrationMapping.DoesNotExist,
            Merch.DoesNotExist,
        ) as error:
            raise CatalogImageImportError(
                f'Mapping Merch осиротел; entity_id={entity_id}',
            ) from error

    @staticmethod
    def _delete_saved_files(saved_files: list[tuple[Any, str]]) -> None:
        for storage, name in saved_files:
            try:
                storage.delete(name)
            except (ClientError, OSError):
                pass

    def _download(self, candidate: ImageCandidate) -> BinaryIO:
        try:
            if settings.USE_S3_MEDIA:
                response = self._get_s3_client().get_object(
                    Bucket=settings.AWS_PRIVATE_STORAGE_BUCKET_NAME,
                    Key=candidate.source_key,
                )
                body = response['Body']
            else:
                body = (
                    self.bundle_root / candidate.asset['bundle_path']
                ).open('rb')
            temporary = SpooledTemporaryFile(max_size=2 * 1024 * 1024)
            digest = hashlib.sha256()
            size = 0
            try:
                while chunk := body.read(1024 * 1024):
                    temporary.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            finally:
                body.close()
            if (
                size != candidate.asset['size']
                or digest.hexdigest().lower()
                != candidate.asset['sha256'].lower()
            ):
                temporary.close()
                raise CatalogImageImportError(
                    'Размер или SHA-256 source не совпадает с manifest; '
                    f'asset_id={candidate.asset["asset_id"]}',
                )
            temporary.seek(0)
            with PillowImage.open(temporary) as image:
                if image.format != candidate.asset['format'] or image.size != (
                    candidate.asset['width'],
                    candidate.asset['height'],
                ):
                    raise CatalogImageImportError(
                        'Формат или размеры source не совпадают с manifest; '
                        f'asset_id={candidate.asset["asset_id"]}',
                    )
                image.verify()
            temporary.seek(0)
            return temporary
        except (ClientError, KeyError, OSError) as error:
            raise CatalogImageImportError(
                'Не удалось прочитать source; '
                f'asset_id={candidate.asset["asset_id"]}',
            ) from error

    def _get_s3_client(self) -> BaseClient:
        if self._s3_client is None:
            # DEBUG botocore включает заголовок Authorization. Команда не
            # должна писать credentials в локальный журнал миграции.
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

    @staticmethod
    def _count(candidates) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for candidate in candidates:
            counts[candidate.entity_type] += 1
        return dict(counts)

    @staticmethod
    def _read_object(path: Path) -> JsonObject:
        value = CatalogImageImporter._read_json(path)
        if not isinstance(value, dict):
            raise CatalogImageImportError(
                f'{path.name}: ожидается JSON object',
            )
        return value

    @staticmethod
    def _read_array(path: Path) -> list[JsonObject]:
        value = CatalogImageImporter._read_json(path)
        if not isinstance(value, list) or not all(
            isinstance(row, dict) for row in value
        ):
            raise CatalogImageImportError(f'{path.name}: ожидается JSON array')
        return value

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            with path.open(encoding='utf-8-sig') as file:
                return json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CatalogImageImportError(
                f'{path.name}: не удалось прочитать JSON',
            ) from error
