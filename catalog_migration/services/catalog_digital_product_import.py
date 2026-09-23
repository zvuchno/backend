"""Create-only импорт цифровых товаров Album и Track из bundle v1.3."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError as DRFValidationError

from catalog_migration.services.catalog_bundle import (
    bundle_root,
    bundle_version,
    mapping_version,
)
from catalog_migration.services.catalog_migration_preflight import (
    CatalogMigrationPreflight,
    PreflightResult,
)

from store.constants import CHAR_PRESET_DIGITAL, ZERO_MONEY
from store.models import (
    Album,
    CatalogMigrationMapping,
    Product,
    ProductVariant,
    Track,
)
from store.services.commerce import ProductService
from store.validators import validate_price

JsonObject = dict[str, Any]


class CatalogDigitalProductImportError(RuntimeError):
    """Безопасная ошибка, блокирующая импорт цифровых товаров."""


@dataclass(frozen=True)
class _Candidate:
    """Один mapped Album или Track и настройки будущего товара."""

    source_entity_id: str
    content: Album | Track
    price: Decimal


@dataclass(frozen=True)
class CatalogDigitalProductImportResult:
    """Агрегированный результат create-only импорта."""

    preflight: PreflightResult
    selected_albums: int
    selected_tracks: int
    skipped_unconfirmed_albums: tuple[str, ...]
    created_products: int
    created_variants: int
    adopted_products: int
    already_mapped: int
    would_create: int
    would_adopt: int
    dry_run: bool

    def render(self) -> str:
        """Формирует отчёт без названий контента."""
        mode = 'DRY-RUN' if self.dry_run else 'PASS'
        skipped = ','.join(self.skipped_unconfirmed_albums) or '-'
        return '\n'.join((
            f'DIGITAL PRODUCT IMPORT {mode}',
            (
                f'selected_albums={self.selected_albums} '
                f'selected_tracks={self.selected_tracks} '
                f'skipped_unconfirmed_albums={len(self.skipped_unconfirmed_albums)}'
            ),
            (
                f'created_products={self.created_products} '
                f'created_variants={self.created_variants} '
                f'adopted_products={self.adopted_products} '
                f'already_mapped={self.already_mapped}'
            ),
            f'would_create={self.would_create} would_adopt={self.would_adopt}',
            f'unconfirmed_entity_id={skipped}',
            'users=0 publication_changes=0 media=0 background_tasks=0',
        ))


class CatalogDigitalProductImporter:
    """Создаёт или безопасно принимает цифровую коммерческую обвязку."""

    product_entity_type = CatalogMigrationMapping.EntityType.PRODUCT
    variant_entity_type = CatalogMigrationMapping.EntityType.VARIANT
    release_entity_type = CatalogMigrationMapping.EntityType.RELEASE
    track_entity_type = CatalogMigrationMapping.EntityType.TRACK

    def __init__(
        self,
        package_root: Path | str,
        *,
        dry_run: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ):
        """Сохраняет путь к пакету и режим без записи."""
        self.package_root = Path(package_root).expanduser()
        self.bundle_version = bundle_version(self.package_root)
        self.mapping_version = mapping_version(self.package_root)
        self.bundle_root = bundle_root(self.package_root)
        self.dry_run = dry_run
        self.progress_callback = progress_callback

    def run(self) -> CatalogDigitalProductImportResult:
        """Запускает preflight, общую проверку и поштучный импорт."""
        preflight = CatalogMigrationPreflight(self.package_root).run()
        if not preflight.passed:
            raise CatalogDigitalProductImportError(preflight.render())

        config = self._read_object(self.package_root / 'import_config.json')
        candidates, selected_albums, selected_tracks, skipped = (
            self._load_candidates(config)
        )
        states = self._validate_all(candidates)

        would_create = sum(state == 'create' for state in states.values())
        would_adopt = sum(state == 'adopt' for state in states.values())
        already_mapped = sum(state == 'mapped' for state in states.values())
        self._report_progress(0, len(candidates))
        if self.dry_run:
            return self._result(
                preflight,
                selected_albums,
                selected_tracks,
                skipped,
                already_mapped=already_mapped,
                would_create=would_create,
                would_adopt=would_adopt,
            )

        created = adopted = 0
        ordered = sorted(candidates, key=lambda item: item.source_entity_id)
        for processed, candidate in enumerate(ordered, start=1):
            outcome = self._process(candidate)
            created += outcome == 'created'
            adopted += outcome == 'adopted'
            self._report_progress(processed, len(ordered))

        return self._result(
            preflight,
            selected_albums,
            selected_tracks,
            skipped,
            created_products=created,
            created_variants=created,
            adopted_products=adopted,
            already_mapped=len(candidates) - created - adopted,
        )

    def _report_progress(self, processed: int, total: int) -> None:
        if self.progress_callback is not None:
            self.progress_callback(processed, total)

    def _result(
        self,
        preflight: PreflightResult,
        selected_albums: int,
        selected_tracks: int,
        skipped: tuple[str, ...],
        **values: int,
    ) -> CatalogDigitalProductImportResult:
        defaults = {
            'created_products': 0,
            'created_variants': 0,
            'adopted_products': 0,
            'already_mapped': 0,
            'would_create': 0,
            'would_adopt': 0,
        }
        defaults.update(values)
        return CatalogDigitalProductImportResult(
            preflight=preflight,
            selected_albums=selected_albums,
            selected_tracks=selected_tracks,
            skipped_unconfirmed_albums=skipped,
            dry_run=self.dry_run,
            **defaults,
        )

    def _load_candidates(
        self,
        config: JsonObject,
    ) -> tuple[list[_Candidate], int, int, tuple[str, ...]]:
        codes = self._read_object(self.package_root / 'artist_codes.json')
        whitelist = set(config['artist_code_whitelist'])
        profile_ids = {
            row['entity_id']
            for row in codes['artists']
            if row['code'] in whitelist
        }
        releases = {
            row['entity_id']: row
            for row in self._read_array(
                self.bundle_root / 'data' / 'releases.json',
            )
            if row['profile_id'] in profile_ids
        }

        candidates: list[_Candidate] = []
        skipped: list[str] = []
        selected_albums = 0
        if config['enabled']['releases']:
            for entity_id, row in releases.items():
                if not self._has_confirmed_release_price(row):
                    skipped.append(entity_id)
                    continue
                selected_albums += 1
                candidates.append(
                    _Candidate(
                        source_entity_id=entity_id,
                        content=self._get_mapped_content(
                            entity_id,
                            self.release_entity_type,
                            Album,
                        ),
                        price=self._parse_price(row, entity_id),
                    ),
                )

        selected_tracks = 0
        if config['enabled']['tracks']:
            for row in self._read_array(
                self.bundle_root / 'data' / 'tracks.json',
            ):
                if row['release_id'] not in releases:
                    continue
                entity_id = row['entity_id']
                track = self._get_mapped_content(
                    entity_id,
                    self.track_entity_type,
                    Track,
                )
                release = self._get_mapped_content(
                    row['release_id'],
                    self.release_entity_type,
                    Album,
                )
                if track.album_id != release.pk:
                    raise CatalogDigitalProductImportError(
                        'Mapping Track конфликтует с mapping Album; '
                        f'entity_id={entity_id}',
                    )
                selected_tracks += 1
                candidates.append(_Candidate(entity_id, track, ZERO_MONEY))

        source_ids = [candidate.source_entity_id for candidate in candidates]
        if len(source_ids) != len(set(source_ids)):
            raise CatalogDigitalProductImportError(
                'Одинаковый entity_id используется для разных цифровых '
                'товаров',
            )
        return (
            candidates,
            selected_albums,
            selected_tracks,
            tuple(sorted(skipped)),
        )

    @staticmethod
    def _has_confirmed_release_price(row: JsonObject) -> bool:
        policy = row.get('price_policy')
        return (
            row.get('price_status') == 'PRESERVED_ACCEPTED_PRICE'
            and row.get('price_requires_review') is False
            and isinstance(policy, dict)
            and policy.get('price_status') == 'PRESERVED_ACCEPTED_PRICE'
            and policy.get('requires_review') is False
            and row.get('target_price') is not None
        )

    @staticmethod
    def _parse_price(row: JsonObject, entity_id: str) -> Decimal:
        try:
            price = Decimal(str(row['target_price']))
            validate_price(price)
        except (
            DRFValidationError,
            InvalidOperation,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise CatalogDigitalProductImportError(
                f'Некорректная подтверждённая цена; entity_id={entity_id}',
            ) from error
        return price

    def _get_mapped_content(
        self,
        entity_id: str,
        entity_type: str,
        model: type[Album] | type[Track],
    ) -> Album | Track:
        mapping = CatalogMigrationMapping.objects.filter(
            bundle_version=self.mapping_version,
            entity_type=entity_type,
            source_entity_id=entity_id,
        ).first()
        if mapping is None:
            raise CatalogDigitalProductImportError(
                f'Mapping {model.__name__} отсутствует; entity_id={entity_id}',
            )
        target = model.objects.filter(pk=mapping.django_pk).first()
        if target is None:
            raise CatalogDigitalProductImportError(
                f'Mapping {model.__name__} указывает на удалённый объект; '
                f'entity_id={entity_id}',
            )
        return target

    def _validate_all(self, candidates: list[_Candidate]) -> dict[str, str]:
        states = {}
        errors = []
        for candidate in candidates:
            try:
                validate_price(candidate.price)
                states[candidate.source_entity_id] = self._classify(candidate)
            except CatalogDigitalProductImportError as error:
                errors.append(str(error))
        if errors:
            raise CatalogDigitalProductImportError('\n'.join(sorted(errors)))
        return states

    def _classify(self, candidate: _Candidate, *, lock: bool = False) -> str:
        entity_id = candidate.source_entity_id
        mappings_qs = CatalogMigrationMapping.objects.filter(
            bundle_version=self.mapping_version,
            entity_type__in=(
                self.product_entity_type,
                self.variant_entity_type,
            ),
            source_entity_id=entity_id,
        )
        if lock:
            mappings_qs = mappings_qs.select_for_update()
        mappings = {row.entity_type: row for row in mappings_qs}
        product_mapping = mappings.get(self.product_entity_type)
        variant_mapping = mappings.get(self.variant_entity_type)
        if (product_mapping is None) != (variant_mapping is None):
            raise self._conflict('Неполный набор mappings', entity_id)

        product = self._content_product(candidate.content, lock=lock)
        if product_mapping is not None:
            mapped_product = Product.objects.filter(
                pk=product_mapping.django_pk,
            ).first()
            mapped_variant = ProductVariant.objects.filter(
                pk=variant_mapping.django_pk,
            ).first()
            if mapped_product is None or mapped_variant is None:
                raise self._conflict(
                    'Mapping указывает на удалённый объект',
                    entity_id,
                )
            if (
                mapped_product.content_id != candidate.content.pk
                or mapped_product.product_type
                != self._product_type(candidate.content)
                or mapped_variant.product_id != mapped_product.pk
                or mapped_variant.property_value != CHAR_PRESET_DIGITAL
                or product is None
                or product.pk != mapped_product.pk
            ):
                raise self._conflict('Mappings товара конфликтуют', entity_id)
            return 'mapped'

        if product is None:
            return 'create'
        variants = list(
            product.variants.filter(
                property_value=CHAR_PRESET_DIGITAL,
            ),
        )
        if len(variants) != 1:
            raise self._conflict(
                'Существующий товар не имеет однозначного digital-варианта',
                entity_id,
            )
        variant = variants[0]
        claims = CatalogMigrationMapping.objects.filter(
            entity_type=self.product_entity_type,
            django_pk=product.pk,
        ).exclude(
            bundle_version=self.mapping_version,
            source_entity_id=entity_id,
        )
        variant_claims = CatalogMigrationMapping.objects.filter(
            entity_type=self.variant_entity_type,
            django_pk=variant.pk,
        ).exclude(
            bundle_version=self.mapping_version,
            source_entity_id=entity_id,
        )
        if claims.exists() or variant_claims.exists():
            raise self._conflict(
                'Существующий товар уже принадлежит другой source-сущности',
                entity_id,
            )
        return 'adopt'

    @transaction.atomic
    def _process(self, candidate: _Candidate) -> str:
        model = type(candidate.content)
        locked_content = model.objects.select_for_update().get(
            pk=candidate.content.pk,
        )
        locked_candidate = _Candidate(
            candidate.source_entity_id,
            locked_content,
            candidate.price,
        )
        state = self._classify(locked_candidate, lock=True)
        if state == 'mapped':
            return 'mapped'
        if state == 'adopt':
            product = self._content_product(locked_content, lock=True)
            variant = product.variants.get(property_value=CHAR_PRESET_DIGITAL)
            self._create_mappings(candidate.source_entity_id, product, variant)
            return 'adopted'

        product = ProductService.ensure_commerce(
            locked_content,
            {'price': candidate.price, 'allow_overpay': False},
        )
        variant = product.variants.get(property_value=CHAR_PRESET_DIGITAL)
        self._create_mappings(candidate.source_entity_id, product, variant)
        return 'created'

    def _create_mappings(self, entity_id, product, variant) -> None:
        try:
            CatalogMigrationMapping.objects.create(
                bundle_version=self.mapping_version,
                entity_type=self.product_entity_type,
                source_entity_id=entity_id,
                django_pk=product.pk,
            )
            CatalogMigrationMapping.objects.create(
                bundle_version=self.mapping_version,
                entity_type=self.variant_entity_type,
                source_entity_id=entity_id,
                django_pk=variant.pk,
            )
        except IntegrityError as error:
            raise CatalogDigitalProductImportError(
                f'Конфликт mappings; entity_id={entity_id}',
            ) from error

    @staticmethod
    def _content_product(content, *, lock: bool = False) -> Product | None:
        field = 'album_id' if isinstance(content, Album) else 'track_id'
        queryset = Product.objects.filter(**{field: content.pk})
        if lock:
            queryset = queryset.select_for_update()
        return queryset.first()

    @staticmethod
    def _product_type(content) -> str:
        if isinstance(content, Album):
            return Product.ProductType.ALBUM
        return Product.ProductType.TRACK

    @staticmethod
    def _conflict(
        message: str,
        entity_id: str,
    ) -> CatalogDigitalProductImportError:
        return CatalogDigitalProductImportError(
            f'{message}; entity_id={entity_id}',
        )

    @staticmethod
    def _read_object(path: Path) -> JsonObject:
        value = CatalogDigitalProductImporter._read_json(path)
        if not isinstance(value, dict):
            raise CatalogDigitalProductImportError(
                f'{path.name}: ожидается JSON object после preflight',
            )
        return value

    @staticmethod
    def _read_array(path: Path) -> list[JsonObject]:
        value = CatalogDigitalProductImporter._read_json(path)
        if not isinstance(value, list) or not all(
            isinstance(row, dict) for row in value
        ):
            raise CatalogDigitalProductImportError(
                f'{path.name}: ожидается JSON array после preflight',
            )
        return value

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            with path.open(encoding='utf-8-sig') as file:
                return json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CatalogDigitalProductImportError(
                f'{path.name}: не удалось прочитать JSON',
            ) from error
