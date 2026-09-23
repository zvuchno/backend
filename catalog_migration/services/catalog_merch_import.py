"""Create-only импорт Merch, Product и ProductVariant из bundle v1.3."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from catalog_migration.services.catalog_bundle import (
    bundle_root,
    bundle_version,
)
from catalog_migration.services.catalog_migration_preflight import (
    CatalogMigrationPreflight,
    PreflightResult,
)
from catalog_migration.services.catalog_migration_registry import (
    CatalogMigrationRegistry,
    CatalogMigrationRegistryError,
)

from store.models import (
    Merch,
    MerchKind,
    Product,
    ProductVariant,
)
from users.models import ArtistProfile

JsonObject = dict[str, Any]


class CatalogMerchImportError(RuntimeError):
    """Безопасная ошибка, блокирующая импорт мерча."""


@dataclass(frozen=True)
class CatalogMerchImportResult:
    """Агрегированный результат импорта без содержимого товаров."""

    preflight: PreflightResult
    selected_merch: int
    selected_variants: int
    created_merch: int
    created_products: int
    created_variants: int
    already_mapped: int
    would_create_merch: int
    would_create_products: int
    would_create_variants: int
    dry_run: bool

    def render(self) -> str:
        """Формирует компактный отчёт команды."""
        mode = 'DRY-RUN' if self.dry_run else 'PASS'
        return '\n'.join((
            f'MERCH IMPORT {mode}',
            (
                f'selected_merch={self.selected_merch} '
                f'selected_variants={self.selected_variants} '
                f'already_mapped={self.already_mapped}'
            ),
            (
                f'created_merch={self.created_merch} '
                f'created_products={self.created_products} '
                f'created_variants={self.created_variants}'
            ),
            (
                f'would_create_merch={self.would_create_merch} '
                f'would_create_products={self.would_create_products} '
                f'would_create_variants={self.would_create_variants}'
            ),
            'users=0 media=0 background_tasks=0 published=0',
        ))


class CatalogMerchImporter:
    """Импортирует Merch вместе с Product, вариантами и mappings."""

    profile_entity_type = 'profile'
    merch_entity_type = 'merch'
    product_entity_type = 'product'
    variant_entity_type = 'variant'

    def __init__(
        self,
        package_root: Path | str,
        *,
        dry_run: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ):
        """Сохраняет путь к пакету и режим запуска."""
        self.package_root = Path(package_root).expanduser()
        self.bundle_version = bundle_version(self.package_root)
        self.bundle_root = bundle_root(self.package_root)
        self.dry_run = dry_run
        self.progress_callback = progress_callback
        self.variants_by_merch: dict[str, list[JsonObject]] = {}
        self.kind_definitions: dict[str, JsonObject] = {}
        self.registry: CatalogMigrationRegistry | None = None

    def run(self) -> CatalogMerchImportResult:
        """Запускает preflight и поштучный атомарный импорт мерча."""
        preflight = CatalogMigrationPreflight(self.package_root).run()
        if not preflight.passed:
            raise CatalogMerchImportError(preflight.render())

        config = self._read_object(self.package_root / 'import_config.json')
        if not config['enabled']['merch']:
            return self._result(preflight=preflight)

        try:
            self.registry = CatalogMigrationRegistry(self.package_root)
        except CatalogMigrationRegistryError as error:
            raise CatalogMerchImportError(str(error)) from error

        selected = self._load_selected(config)
        profile_targets = self._validate_profile_mappings(selected)
        kind_targets = self._validate_kinds(selected)
        self._validate_fields(selected, profile_targets, kind_targets)
        mapped = self._validate_mappings(selected, profile_targets)
        self._report_progress(0, len(selected))

        selected_variants = sum(
            len(rows) for rows in self.variants_by_merch.values()
        )
        mapped_variants = sum(
            len(self.variants_by_merch[entity_id]) for entity_id in mapped
        )
        if self.dry_run:
            pending = len(selected) - len(mapped)
            return self._result(
                preflight=preflight,
                selected_merch=len(selected),
                selected_variants=selected_variants,
                already_mapped=len(mapped),
                would_create_merch=pending,
                would_create_products=pending,
                would_create_variants=selected_variants - mapped_variants,
            )

        created_merch = created_products = created_variants = 0
        for processed, entity_id in enumerate(sorted(selected), start=1):
            if entity_id in mapped:
                self._report_progress(processed, len(selected))
                continue
            variant_count = self._create_merch(selected[entity_id])
            created_merch += 1
            created_products += 1
            created_variants += variant_count
            self._report_progress(processed, len(selected))

        return self._result(
            preflight=preflight,
            selected_merch=len(selected),
            selected_variants=selected_variants,
            created_merch=created_merch,
            created_products=created_products,
            created_variants=created_variants,
            already_mapped=len(selected) - created_merch,
        )

    def _report_progress(self, processed: int, total: int) -> None:
        if self.progress_callback is not None:
            self.progress_callback(processed, total)

    def _result(
        self,
        *,
        preflight: PreflightResult,
        **values: int,
    ) -> CatalogMerchImportResult:
        defaults = {
            'selected_merch': 0,
            'selected_variants': 0,
            'created_merch': 0,
            'created_products': 0,
            'created_variants': 0,
            'already_mapped': 0,
            'would_create_merch': 0,
            'would_create_products': 0,
            'would_create_variants': 0,
        }
        defaults.update(values)
        return CatalogMerchImportResult(
            preflight=preflight,
            dry_run=self.dry_run,
            **defaults,
        )

    def _load_selected(self, config: JsonObject) -> dict[str, JsonObject]:
        codes = self._read_object(self.package_root / 'artist_codes.json')
        whitelist = set(config['artist_code_whitelist'])
        profile_ids = {
            row['entity_id']
            for row in codes['artists']
            if row['code'] in whitelist
        }
        merch = self._read_array(self.bundle_root / 'data' / 'merch.json')
        selected = {
            row['entity_id']: row
            for row in merch
            if row['profile_id'] in profile_ids
        }
        variants = self._read_array(
            self.bundle_root / 'data' / 'variants.json',
        )
        self.variants_by_merch = {entity_id: [] for entity_id in selected}
        for row in variants:
            if row['merch_id'] in selected:
                self.variants_by_merch[row['merch_id']].append(row)
        return selected

    def _validate_profile_mappings(
        self,
        selected: dict[str, JsonObject],
    ) -> dict[str, ArtistProfile]:
        profile_ids = {row['profile_id'] for row in selected.values()}
        registry = self._get_registry()
        mappings = {
            entity_id: django_pk
            for entity_id, django_pk in registry.get_mappings(
                self.profile_entity_type,
            ).items()
            if entity_id in profile_ids
        }
        targets = ArtistProfile.objects.in_bulk(mappings.values())
        errors = []
        for entity_id, row in selected.items():
            mapping = mappings.get(row['profile_id'])
            if mapping is None:
                errors.append(
                    'Mapping ArtistProfile отсутствует; '
                    f'entity_id={entity_id}',
                )
            elif mapping not in targets:
                errors.append(
                    'Mapping ArtistProfile указывает на удалённый профиль; '
                    f'entity_id={entity_id}',
                )
        if errors:
            raise CatalogMerchImportError('\n'.join(sorted(errors)))
        return {
            entity_id: targets[mappings[row['profile_id']]]
            for entity_id, row in selected.items()
        }

    def _validate_kinds(
        self,
        selected: dict[str, JsonObject],
    ) -> dict[str, MerchKind]:
        reference = self._read_object(
            self.bundle_root / 'reference' / 'merch_kinds.json',
        )
        rows = reference.get('kinds')
        if not isinstance(rows, list) or not all(
            isinstance(row, dict) for row in rows
        ):
            raise CatalogMerchImportError(
                'merch_kinds.json: ожидается массив kinds',
            )
        self.kind_definitions = {
            row.get('slug'): row
            for row in rows
            if isinstance(row.get('slug'), str)
        }
        slugs = {
            row.get('target_kind_slug')
            for row in selected.values()
            if row.get('target_kind_slug') is not None
        }
        unknown = sorted(
            slug for slug in slugs if slug not in self.kind_definitions
        )
        if unknown:
            raise CatalogMerchImportError(
                f'Неизвестный target_kind_slug; slug={",".join(unknown)}',
            )
        existing = MerchKind.objects.in_bulk(slugs, field_name='slug')
        invalid = []
        for slug in slugs:
            definition = self.kind_definitions[slug]
            try:
                candidate = MerchKind(
                    name=definition['name'],
                    slug=slug,
                    is_carrier=definition['is_carrier'],
                    is_active=True,
                )
                candidate.full_clean(validate_unique=False)
            except (KeyError, TypeError, ValidationError, ValueError):
                invalid.append(slug)
                continue
            current = existing.get(slug)
            if current is not None and (
                current.name != candidate.name
                or current.is_carrier != candidate.is_carrier
            ):
                invalid.append(slug)
        if invalid:
            raise CatalogMerchImportError(
                'MerchKind конфликтует со справочником bundle; '
                f'slug={",".join(sorted(invalid))}',
            )
        return existing

    def _validate_fields(
        self,
        selected: dict[str, JsonObject],
        profile_targets: dict[str, ArtistProfile],
        kind_targets: dict[str, MerchKind],
    ) -> None:
        invalid = []
        for entity_id, row in selected.items():
            try:
                if row.get('release_id') is not None:
                    raise ValueError('release_id не подтверждён для импорта')
                merch = self._build_merch(
                    row,
                    artist=profile_targets[entity_id],
                    kind=kind_targets.get(row.get('target_kind_slug')),
                )
                # kind допускает NULL в БД, хотя form-level blank=False.
                # Неподтверждённые виды bundle сохраняем как NULL.
                merch.full_clean(exclude=('kind',), validate_unique=False)
                product = self._build_product(row, merch=None)
                product.full_clean(
                    exclude=('album', 'track', 'merch'),
                    validate_unique=False,
                    validate_constraints=False,
                )
                for variant_row in self.variants_by_merch[entity_id]:
                    variant = self._build_variant(variant_row, product=None)
                    variant.full_clean(
                        exclude=('product',),
                        validate_unique=False,
                        validate_constraints=False,
                    )
            except (
                InvalidOperation,
                KeyError,
                TypeError,
                ValidationError,
                ValueError,
            ):
                invalid.append(entity_id)
        if invalid:
            raise CatalogMerchImportError(
                'Merch не прошёл предварительную Django-валидацию; '
                f'entity_id={",".join(sorted(invalid))}',
            )

    def _validate_mappings(
        self,
        selected: dict[str, JsonObject],
        profile_targets: dict[str, ArtistProfile],
    ) -> set[str]:
        merch_ids = set(selected)
        variant_ids = {
            row['entity_id']
            for rows in self.variants_by_merch.values()
            for row in rows
        }
        registry = self._get_registry()
        mappings = {
            entity_type: {
                entity_id: django_pk
                for entity_id, django_pk in registry.get_mappings(
                    entity_type,
                ).items()
                if entity_id
                in (
                    variant_ids
                    if entity_type == self.variant_entity_type
                    else merch_ids
                )
            }
            for entity_type in (
                self.merch_entity_type,
                self.product_entity_type,
                self.variant_entity_type,
            )
        }
        merch_targets = Merch.objects.in_bulk(
            mappings[self.merch_entity_type].values(),
        )
        product_targets = Product.objects.in_bulk(
            mappings[self.product_entity_type].values(),
        )
        variant_targets = ProductVariant.objects.in_bulk(
            mappings[self.variant_entity_type].values(),
        )

        complete = set()
        errors = []
        for entity_id in selected:
            variant_rows = self.variants_by_merch[entity_id]
            merch_mapping = mappings[self.merch_entity_type].get(entity_id)
            product_mapping = mappings[self.product_entity_type].get(entity_id)
            variant_mappings = [
                mappings[self.variant_entity_type].get(row['entity_id'])
                for row in variant_rows
            ]
            present = [
                merch_mapping is not None,
                product_mapping is not None,
                *(row is not None for row in variant_mappings),
            ]
            if not any(present):
                continue
            if not all(present):
                errors.append(
                    f'Неполный набор mappings; entity_id={entity_id}',
                )
                continue

            merch = merch_targets.get(merch_mapping)
            product = product_targets.get(product_mapping)
            variants = [
                variant_targets.get(mapping) for mapping in variant_mappings
            ]
            if (
                merch is None
                or product is None
                or any(variant is None for variant in variants)
            ):
                errors.append(
                    'Mapping указывает на удалённый объект; '
                    f'entity_id={entity_id}',
                )
            elif merch.artist_id != profile_targets[entity_id].pk:
                errors.append(
                    'Mapping Merch конфликтует с mapping ArtistProfile; '
                    f'entity_id={entity_id}',
                )
            elif product.merch_id != merch.pk or any(
                variant.product_id != product.pk for variant in variants
            ):
                errors.append(
                    f'Mappings товара конфликтуют; entity_id={entity_id}',
                )
            else:
                complete.add(entity_id)
        if errors:
            raise CatalogMerchImportError('\n'.join(sorted(errors)))
        return complete

    def _create_merch(self, row: JsonObject) -> int:
        entity_id = row['entity_id']
        registry = self._get_registry()
        try:
            with transaction.atomic():
                variant_rows = self.variants_by_merch[entity_id]
                mapping_keys = (
                    (self.merch_entity_type, entity_id),
                    (self.product_entity_type, entity_id),
                    *(
                        (self.variant_entity_type, variant['entity_id'])
                        for variant in variant_rows
                    ),
                )
                if any(
                    registry.get_mapping(entity_type, source_entity_id)
                    is not None
                    for entity_type, source_entity_id in mapping_keys
                ):
                    raise CatalogMerchImportError(
                        'Неполный или конкурентный mapping; '
                        f'entity_id={entity_id}',
                    )

                new_mappings: dict[tuple[str, str], int] = {}
                artist = self._get_profile_target(row)
                kind = self._get_kind_target(row.get('target_kind_slug'))
                merch = self._build_merch(row, artist=artist, kind=kind)
                merch.full_clean(exclude=('kind',), validate_unique=False)
                merch.save(force_insert=True)
                self._create_mapping(
                    new_mappings,
                    self.merch_entity_type,
                    entity_id,
                    merch.pk,
                )

                product = self._build_product(row, merch=merch)
                product.full_clean(validate_unique=False)
                product.save(force_insert=True)
                self._create_mapping(
                    new_mappings,
                    self.product_entity_type,
                    entity_id,
                    product.pk,
                )

                for variant_row in variant_rows:
                    variant = self._build_variant(variant_row, product=product)
                    variant.full_clean(validate_unique=False)
                    # ProductVariant.save() генерирует проектный SKU после PK.
                    variant.save(force_insert=True)
                    self._create_mapping(
                        new_mappings,
                        self.variant_entity_type,
                        variant_row['entity_id'],
                        variant.pk,
                    )
                try:
                    registry.add_mappings(new_mappings)
                except CatalogMigrationRegistryError as error:
                    raise CatalogMerchImportError(
                        'Не удалось записать mappings товара; '
                        'транзакция БД отменена; '
                        f'entity_id={entity_id}',
                    ) from error
                return len(variant_rows)
        except CatalogMerchImportError:
            raise
        except (
            InvalidOperation,
            KeyError,
            TypeError,
            ValidationError,
            ValueError,
        ) as error:
            raise CatalogMerchImportError(
                f'Merch не прошёл Django-валидацию; entity_id={entity_id}',
            ) from error
        except IntegrityError as error:
            raise CatalogMerchImportError(
                f'Конфликт целостности БД; entity_id={entity_id}',
            ) from error

    def _get_profile_target(self, row: JsonObject) -> ArtistProfile:
        mapping = self._get_registry().get_mapping(
            self.profile_entity_type,
            row['profile_id'],
        )
        if mapping is None:
            raise CatalogMerchImportError(
                'Mapping ArtistProfile отсутствует; '
                f'entity_id={row["entity_id"]}',
            )
        artist = ArtistProfile.objects.filter(pk=mapping).first()
        if artist is None:
            raise CatalogMerchImportError(
                'Mapping ArtistProfile указывает на удалённый профиль; '
                f'entity_id={row["entity_id"]}',
            )
        return artist

    def _get_kind_target(self, slug: str | None) -> MerchKind | None:
        if slug is None:
            return None
        from catalog_migration.services.catalog_reference_seed import (
            ensure_reference,
        )

        definition = self.kind_definitions[slug]
        try:
            current, _ = ensure_reference(
                MerchKind,
                {
                    'slug': slug,
                    'name': definition['name'],
                    'is_carrier': definition['is_carrier'],
                },
                apply=True,
            )
        except ValidationError as error:
            raise CatalogMerchImportError(
                f'MerchKind конфликтует со справочником bundle; slug={slug}',
            ) from error
        return current

    @staticmethod
    def _build_merch(
        row: JsonObject,
        *,
        artist: ArtistProfile,
        kind: MerchKind | None,
    ) -> Merch:
        description = row.get('description')
        if description is None:
            description = ''
        if not isinstance(description, str):
            raise TypeError('description должен быть строкой или null')
        return Merch(
            artist=artist,
            created_by=None,
            payout_recipient=None,
            name=row['title'],
            description=description,
            kind=kind,
            album=None,
            is_active=True,
            is_published=False,
        )

    @staticmethod
    def _build_product(row: JsonObject, *, merch: Merch | None) -> Product:
        price = Decimal(str(row['target_price']))
        property_name = row.get('property_name')
        if property_name is None:
            property_name = ''
        if not isinstance(property_name, str):
            raise TypeError('property_name должен быть строкой или null')
        return Product(
            product_type=Product.ProductType.MERCH,
            merch=merch,
            price=price,
            allow_overpay=False,
            property_name=property_name,
        )

    @staticmethod
    def _build_variant(
        row: JsonObject,
        *,
        product: Product | None,
    ) -> ProductVariant:
        if row.get('sku_strategy') != 'BACKEND_GENERATED':
            raise ValueError('Неподдерживаемая стратегия SKU')
        if row.get('final_sku') is not None:
            raise ValueError('final_sku должен генерироваться backend')
        return ProductVariant(
            product=product,
            sku='',
            stock=row['target_stock'],
            property_value=row['property_value'],
            is_active=True,
        )

    @staticmethod
    def _create_mapping(
        mappings: dict[tuple[str, str], int],
        entity_type: str,
        entity_id: str,
        pk: int,
    ) -> None:
        key = (entity_type, entity_id)
        if key in mappings:
            raise CatalogMerchImportError(
                'Повторяющийся source entity для mapping; '
                f'entity_type={entity_type}; entity_id={entity_id}',
            )
        mappings[key] = pk

    def _get_registry(self) -> CatalogMigrationRegistry:
        if self.registry is None:
            raise CatalogMerchImportError(
                'Реестр mappings не инициализирован.',
            )
        return self.registry

    @staticmethod
    def _read_object(path: Path) -> JsonObject:
        value = CatalogMerchImporter._read_json(path)
        if not isinstance(value, dict):
            raise CatalogMerchImportError(
                f'{path.name}: ожидается JSON object после preflight',
            )
        return value

    @staticmethod
    def _read_array(path: Path) -> list[JsonObject]:
        value = CatalogMerchImporter._read_json(path)
        if not isinstance(value, list) or not all(
            isinstance(row, dict) for row in value
        ):
            raise CatalogMerchImportError(
                f'{path.name}: ожидается JSON array после preflight',
            )
        return value

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            with path.open(encoding='utf-8-sig') as file:
                return json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CatalogMerchImportError(
                f'{path.name}: не удалось прочитать JSON',
            ) from error
