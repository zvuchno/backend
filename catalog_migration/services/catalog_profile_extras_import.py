"""Create-only импорт дополнительных данных профилей migration-v1.3."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from catalog_migration.services.catalog_bundle import (
    bundle_version,
    mapping_version,
)
from catalog_migration.services.catalog_migration_preflight import (
    CatalogMigrationPreflight,
    PreflightResult,
)

from store.models import CatalogMigrationMapping
from users.models import (
    ArtistContact,
    ArtistProfile,
    ArtistShippingPoint,
    ArtistSocial,
    ArtistStoreSettings,
)

JsonObject = dict[str, Any]


class CatalogProfileExtrasImportError(RuntimeError):
    """Ошибка, безопасно блокирующая импорт дополнительных данных."""


@dataclass(frozen=True)
class CategoryResult:
    """Счётчики одной категории ведомости."""

    selected: int = 0
    created: int = 0
    existing: int = 0
    would_create: int = 0


@dataclass(frozen=True)
class CatalogProfileExtrasImportResult:
    """Результат импорта четырёх категорий дополнительных данных."""

    preflight: PreflightResult
    contacts: CategoryResult
    socials: CategoryResult
    telegram: CategoryResult
    cdek: CategoryResult
    skipped_manual_review: int
    skipped_ambiguous_telegram: int
    skipped_entity_ids: tuple[str, ...]
    dry_run: bool

    def render(self) -> str:
        """Возвращает компактный обезличенный отчёт."""
        mode = 'DRY-RUN' if self.dry_run else 'PASS'
        lines = [f'PROFILE EXTRAS IMPORT {mode}']
        for name in ('contacts', 'socials', 'telegram', 'cdek'):
            value = getattr(self, name)
            lines.append(
                f'{name}: selected={value.selected} created={value.created} '
                f'existing={value.existing} '
                f'would_create={value.would_create}',
            )
        skipped = ','.join(self.skipped_entity_ids) or '-'
        lines.extend((
            f'skipped_manual_review={self.skipped_manual_review}',
            (f'skipped_ambiguous_telegram={self.skipped_ambiguous_telegram}'),
            f'skipped_entity_id={skipped}',
            'users=0 shipping_enabled_changes=0 external_calls=0',
        ))
        return '\n'.join(lines)


@dataclass
class _ProfilePlan:
    """Дополнительные данные одного source-профиля."""

    entity_id: str
    profile: ArtistProfile
    contacts: list[JsonObject]
    socials: list[JsonObject]
    telegram_chat_id: int | None = None
    cdek: JsonObject | None = None


class CatalogProfileExtrasImporter:
    """Импортирует дополнительные данные только в mapped-профили."""

    profile_entity_type = CatalogMigrationMapping.EntityType.PROFILE

    def __init__(
        self,
        package_root: Path | str,
        *,
        dry_run: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ):
        """Сохраняет путь к локальному пакету и режим запуска."""
        self.package_root = Path(package_root).expanduser()
        self.bundle_version = bundle_version(self.package_root)
        self.mapping_version = mapping_version(self.package_root)
        self.dry_run = dry_run
        self.progress_callback = progress_callback
        self.skipped_manual_review = 0
        self.skipped_ambiguous_telegram = 0
        self.skipped_entity_ids: set[str] = set()

    def run(self) -> CatalogProfileExtrasImportResult:
        """Запускает preflight, полную проверку и поштучный импорт."""
        preflight = CatalogMigrationPreflight(self.package_root).run()
        if not preflight.passed:
            raise CatalogProfileExtrasImportError(preflight.render())

        config = self._read_object(self.package_root / 'import_config.json')
        plans = self._load_plans(config)
        states = self._validate_all(plans)
        selected = self._selected_counts(plans)
        existing = self._existing_counts(states)
        pending = {name: selected[name] - existing[name] for name in selected}
        self._report_progress(0, len(plans))
        if self.dry_run:
            return self._result(
                preflight,
                selected,
                existing=existing,
                would_create=pending,
            )

        created = {name: 0 for name in selected}
        ordered = sorted(plans.values(), key=lambda item: item.entity_id)
        for processed, plan in enumerate(ordered, start=1):
            outcome = self._apply_profile(plan)
            for name, count in outcome.items():
                created[name] += count
            self._report_progress(processed, len(ordered))
        return self._result(
            preflight,
            selected,
            created=created,
            existing={
                name: selected[name] - created[name] for name in selected
            },
        )

    def _report_progress(self, processed: int, total: int) -> None:
        if self.progress_callback is not None:
            self.progress_callback(processed, total)

    def _result(
        self,
        preflight: PreflightResult,
        selected: dict[str, int],
        *,
        created: dict[str, int] | None = None,
        existing: dict[str, int] | None = None,
        would_create: dict[str, int] | None = None,
    ) -> CatalogProfileExtrasImportResult:
        created = created or {}
        existing = existing or {}
        would_create = would_create or {}

        def category(name: str) -> CategoryResult:
            return CategoryResult(
                selected=selected[name],
                created=created.get(name, 0),
                existing=existing.get(name, 0),
                would_create=would_create.get(name, 0),
            )

        return CatalogProfileExtrasImportResult(
            preflight=preflight,
            contacts=category('contacts'),
            socials=category('socials'),
            telegram=category('telegram'),
            cdek=category('cdek'),
            skipped_manual_review=self.skipped_manual_review,
            skipped_ambiguous_telegram=self.skipped_ambiguous_telegram,
            skipped_entity_ids=tuple(sorted(self.skipped_entity_ids)),
            dry_run=self.dry_run,
        )

    def _load_plans(self, config: JsonObject) -> dict[str, _ProfilePlan]:
        selected_ids = self._selected_profile_ids(config)
        raw: dict[str, dict[str, Any]] = {}
        enabled = config['enabled']
        if enabled['public_contacts']:
            self._load_public_contacts(raw, selected_ids)

        if enabled['telegram']:
            self._load_telegram(raw, selected_ids)

        if enabled['cdek']:
            self._load_cdek(raw, selected_ids)

        profiles = self._mapped_profiles(set(raw))
        return {
            entity_id: _ProfilePlan(
                entity_id=entity_id,
                profile=profiles[entity_id],
                **fields,
            )
            for entity_id, fields in raw.items()
        }

    @staticmethod
    def _raw_values(
        raw: dict[str, dict[str, Any]],
        entity_id: str,
    ) -> dict[str, Any]:
        return raw.setdefault(
            entity_id,
            {
                'contacts': [],
                'socials': [],
                'telegram_chat_id': None,
                'cdek': None,
            },
        )

    def _load_public_contacts(
        self,
        raw: dict[str, dict[str, Any]],
        selected_ids: set[str],
    ) -> None:
        document = self._read_object(
            self.package_root / 'public_contacts.json',
        )
        blocked = self._manual_review_pairs(document)
        for row in document['profiles']:
            entity_id = row['entity_id']
            if entity_id not in selected_ids:
                continue
            target = self._raw_values(raw, entity_id)
            for category in ('contacts', 'socials'):
                for item in row[category]:
                    if (entity_id, item['value']) in blocked:
                        self.skipped_manual_review += 1
                        self.skipped_entity_ids.add(entity_id)
                    else:
                        target[category].append(item)

    def _load_telegram(
        self,
        raw: dict[str, dict[str, Any]],
        selected_ids: set[str],
    ) -> None:
        document = self._read_object(
            self.package_root / 'telegram_bindings.json',
        )
        for row in document['bindings']:
            entity_id = row['entity_id']
            if entity_id not in selected_ids:
                continue
            if not (
                row['matched_in_both_sources'] is True
                and row['sources_match'] is True
            ):
                self.skipped_ambiguous_telegram += 1
                self.skipped_entity_ids.add(entity_id)
                continue
            self._raw_values(raw, entity_id)['telegram_chat_id'] = row[
                'chat_id'
            ]

    def _load_cdek(
        self,
        raw: dict[str, dict[str, Any]],
        selected_ids: set[str],
    ) -> None:
        document = self._read_object(
            self.package_root / 'cdek_shipping_points.json',
        )
        for row in document['points']:
            entity_id = row['entity_id']
            if entity_id not in selected_ids:
                continue
            if not self._usable_cdek(row):
                self.skipped_entity_ids.add(entity_id)
                continue
            self._raw_values(raw, entity_id)['cdek'] = row

    def _selected_profile_ids(self, config: JsonObject) -> set[str]:
        document = self._read_object(self.package_root / 'artist_codes.json')
        whitelist = set(config['artist_code_whitelist'])
        return {
            row['entity_id']
            for row in document['artists']
            if row['code'] in whitelist
        }

    @staticmethod
    def _manual_review_pairs(document: JsonObject) -> set[tuple[str, str]]:
        blocked = set()
        for row in document['manual_review']:
            value = row.get('value')
            if not isinstance(value, str):
                continue
            for entity_id in row['entity_ids']:
                blocked.add((entity_id, value))
        return blocked

    @staticmethod
    def _usable_cdek(row: JsonObject) -> bool:
        return (
            row.get('status') == 'pending_api'
            and all(
                isinstance(row.get(field), str) and bool(row[field].strip())
                for field in ('pvz_code', 'city_code', 'pvz_city', 'address')
            )
            and not row.get('missing_fields')
        )

    def _mapped_profiles(
        self,
        entity_ids: set[str],
    ) -> dict[str, ArtistProfile]:
        mappings = {
            row.source_entity_id: row
            for row in CatalogMigrationMapping.objects.filter(
                bundle_version=self.mapping_version,
                entity_type=self.profile_entity_type,
                source_entity_id__in=entity_ids,
            )
        }
        targets = ArtistProfile.objects.in_bulk(
            row.django_pk for row in mappings.values()
        )
        errors = []
        for entity_id in entity_ids:
            mapping = mappings.get(entity_id)
            if mapping is None:
                errors.append(
                    'Mapping ArtistProfile отсутствует; '
                    f'entity_id={entity_id}',
                )
            elif mapping.django_pk not in targets:
                errors.append(
                    'Mapping ArtistProfile указывает на удалённый профиль; '
                    f'entity_id={entity_id}',
                )
        if errors:
            raise CatalogProfileExtrasImportError('\n'.join(sorted(errors)))
        return {
            entity_id: targets[mapping.django_pk]
            for entity_id, mapping in mappings.items()
        }

    def _validate_all(
        self,
        plans: dict[str, _ProfilePlan],
    ) -> dict[str, dict[str, int]]:
        states = {}
        errors = []
        for entity_id, plan in plans.items():
            try:
                self._validate_fields(plan)
                states[entity_id] = self._classify(plan)
            except ValidationError:
                errors.append(
                    'Дополнительные данные не прошли Django-валидацию; '
                    f'entity_id={entity_id}',
                )
            except CatalogProfileExtrasImportError as error:
                errors.append(
                    f'{error}; entity_id={entity_id}'
                    if 'entity_id=' not in str(error)
                    else str(error),
                )
        if errors:
            raise CatalogProfileExtrasImportError('\n'.join(sorted(errors)))
        return states

    @staticmethod
    def _validate_fields(plan: _ProfilePlan) -> None:
        for row in plan.contacts:
            ArtistContact(
                artist=plan.profile,
                label=row['label'],
                value=row['value'],
            ).full_clean(validate_unique=False)
        for row in plan.socials:
            ArtistSocial(
                artist=plan.profile,
                label=row['label'],
                value=row['value'],
            ).full_clean(validate_unique=False)
        if plan.cdek is not None:
            ArtistShippingPoint(
                artist=plan.profile,
                pvz_code=plan.cdek['pvz_code'],
                city_code=plan.cdek['city_code'],
                city=plan.cdek['pvz_city'],
                address=plan.cdek['address'],
            ).full_clean(validate_unique=False)

    def _classify(self, plan: _ProfilePlan) -> dict[str, int]:
        existing_contacts = set(
            plan.profile.contacts.values_list(
                'label',
                'value',
            ),
        )
        existing_socials = set(
            plan.profile.socials.values_list(
                'label',
                'value',
            ),
        )
        result = {
            'contacts': sum(
                (row['label'], row['value']) in existing_contacts
                for row in plan.contacts
            ),
            'socials': sum(
                (row['label'], row['value']) in existing_socials
                for row in plan.socials
            ),
            'telegram': 0,
            'cdek': int(
                plan.cdek is not None
                and ArtistShippingPoint.objects.filter(
                    artist=plan.profile,
                ).exists(),
            ),
        }
        self._validate_telegram_conflict(plan)
        if (
            plan.telegram_chat_id is not None
            and plan.profile.telegram_chat_id == plan.telegram_chat_id
        ):
            result['telegram'] = 1
        if (
            plan.cdek is not None
            and result['cdek'] == 0
            and ArtistStoreSettings.objects.filter(
                artist=plan.profile,
                shipping_enabled=True,
            ).exists()
        ):
            raise CatalogProfileExtrasImportError(
                f'У профиля уже включена доставка; entity_id={plan.entity_id}',
            )
        return result

    @staticmethod
    def _validate_telegram_conflict(plan: _ProfilePlan) -> None:
        chat_id = plan.telegram_chat_id
        if chat_id is None:
            return
        if plan.profile.telegram_chat_id not in (None, chat_id):
            raise CatalogProfileExtrasImportError(
                'У профиля уже указан другой telegram_chat_id; '
                f'entity_id={plan.entity_id}',
            )
        if (
            ArtistProfile.objects
            .filter(
                telegram_chat_id=chat_id,
            )
            .exclude(pk=plan.profile.pk)
            .exists()
        ):
            raise CatalogProfileExtrasImportError(
                'telegram_chat_id уже занят другим профилем; '
                f'entity_id={plan.entity_id}',
            )

    @staticmethod
    def _selected_counts(plans: dict[str, _ProfilePlan]) -> dict[str, int]:
        return {
            'contacts': sum(len(plan.contacts) for plan in plans.values()),
            'socials': sum(len(plan.socials) for plan in plans.values()),
            'telegram': sum(
                plan.telegram_chat_id is not None for plan in plans.values()
            ),
            'cdek': sum(plan.cdek is not None for plan in plans.values()),
        }

    @staticmethod
    def _existing_counts(
        states: dict[str, dict[str, int]],
    ) -> dict[str, int]:
        return {
            name: sum(state[name] for state in states.values())
            for name in ('contacts', 'socials', 'telegram', 'cdek')
        }

    @transaction.atomic
    def _apply_profile(self, plan: _ProfilePlan) -> dict[str, int]:
        profile = ArtistProfile.objects.select_for_update().get(
            pk=plan.profile.pk,
        )
        locked = _ProfilePlan(
            entity_id=plan.entity_id,
            profile=profile,
            contacts=plan.contacts,
            socials=plan.socials,
            telegram_chat_id=plan.telegram_chat_id,
            cdek=plan.cdek,
        )
        self._validate_telegram_conflict(locked)
        created = {
            name: 0 for name in ('contacts', 'socials', 'telegram', 'cdek')
        }
        try:
            for row in locked.contacts:
                _, was_created = ArtistContact.objects.get_or_create(
                    artist=profile,
                    label=row['label'],
                    value=row['value'],
                )
                created['contacts'] += was_created
            for row in locked.socials:
                _, was_created = ArtistSocial.objects.get_or_create(
                    artist=profile,
                    label=row['label'],
                    value=row['value'],
                )
                created['socials'] += was_created

            if locked.telegram_chat_id is not None:
                if profile.telegram_chat_id is None:
                    profile.telegram_chat_id = locked.telegram_chat_id
                    profile.save(update_fields=('telegram_chat_id',))
                    created['telegram'] = 1

            if (
                locked.cdek is not None
                and not ArtistShippingPoint.objects.filter(
                    artist=profile,
                ).exists()
            ):
                settings, _ = ArtistStoreSettings.objects.get_or_create(
                    artist=profile,
                    defaults={'shipping_enabled': False},
                )
                if settings.shipping_enabled:
                    raise CatalogProfileExtrasImportError(
                        'У профиля уже включена доставка; '
                        f'entity_id={locked.entity_id}',
                    )
                _, created['cdek'] = ArtistShippingPoint.objects.get_or_create(
                    artist=profile,
                    defaults={
                        'pvz_code': locked.cdek['pvz_code'],
                        'city_code': locked.cdek['city_code'],
                        'city': locked.cdek['pvz_city'],
                        'address': locked.cdek['address'],
                    },
                )
        except IntegrityError as error:
            raise CatalogProfileExtrasImportError(
                f'Конфликт целостности БД; entity_id={locked.entity_id}',
            ) from error
        return created

    @staticmethod
    def _read_object(path: Path) -> JsonObject:
        try:
            with path.open(encoding='utf-8-sig') as source:
                value = json.load(source)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CatalogProfileExtrasImportError(
                f'{path.name}: не удалось прочитать JSON',
            ) from error
        if not isinstance(value, dict):
            raise CatalogProfileExtrasImportError(
                f'{path.name}: ожидается JSON object после preflight',
            )
        return value
