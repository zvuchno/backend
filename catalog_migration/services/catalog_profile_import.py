"""Идемпотентный импорт профилей из замороженного bundle v1.3."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from django.core.exceptions import ValidationError
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
from catalog_migration.services.catalog_migration_registry import (
    CatalogMigrationRegistry,
    CatalogMigrationRegistryError,
)

from users.models import ArtistProfile, ArtistProfileType

JsonObject = dict[str, Any]


class CatalogProfileImportError(RuntimeError):
    """Безопасная ошибка, блокирующая импорт профилей."""


@dataclass(frozen=True)
class CatalogProfileImportResult:
    """Агрегированный результат импорта без персональных данных."""

    preflight: PreflightResult
    selected: int
    created: int
    already_mapped: int
    would_create: int
    dry_run: bool

    def render(self) -> str:
        """Формирует компактный отчёт команды."""
        mode = 'DRY-RUN' if self.dry_run else 'PASS'
        return '\n'.join((
            f'PROFILE IMPORT {mode}',
            (
                f'selected={self.selected} created={self.created} '
                f'already_mapped={self.already_mapped} '
                f'would_create={self.would_create}'
            ),
            'slug_normalization=lowercase',
        ))


class CatalogProfileImporter:
    """Импортирует ArtistProfile и записывает их в файловый реестр."""

    entity_type = 'profile'

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
        self.mapping_version = mapping_version(self.package_root)
        self.bundle_root = bundle_root(self.package_root)
        self.dry_run = dry_run
        self.progress_callback = progress_callback
        self.codes_by_entity: dict[str, str] = {}
        self.registry: CatalogMigrationRegistry | None = None

    def run(self) -> CatalogProfileImportResult:
        """Запускает preflight и идемпотентный импорт профилей."""
        preflight = CatalogMigrationPreflight(self.package_root).run()
        if not preflight.passed:
            raise CatalogProfileImportError(preflight.render())

        config = self._read_object(self.package_root / 'import_config.json')
        if not config['enabled']['profiles']:
            return CatalogProfileImportResult(
                preflight=preflight,
                selected=0,
                created=0,
                already_mapped=0,
                would_create=0,
                dry_run=self.dry_run,
            )

        try:
            self.registry = CatalogMigrationRegistry(self.package_root)
        except CatalogMigrationRegistryError as error:
            raise CatalogProfileImportError(str(error)) from error
        selected = self._load_selected_profiles(config)
        self._validate_selected_relations(selected)
        self._validate_profile_fields(selected)
        mapped = self._validate_database_state(selected)
        self._report_progress(0, len(selected))
        would_create = len(selected) - len(mapped)
        if self.dry_run:
            return CatalogProfileImportResult(
                preflight=preflight,
                selected=len(selected),
                created=0,
                already_mapped=len(mapped),
                would_create=would_create,
                dry_run=True,
            )

        created = 0
        ordered = sorted(
            selected.values(),
            key=lambda row: (
                row['profile_type'] != 'LABEL',
                row['entity_id'],
            ),
        )
        for processed, row in enumerate(ordered, start=1):
            if row['entity_id'] in mapped:
                self._report_progress(processed, len(ordered))
                continue
            if self._create_profile(row):
                created += 1
            self._report_progress(processed, len(ordered))

        return CatalogProfileImportResult(
            preflight=preflight,
            selected=len(selected),
            created=created,
            already_mapped=len(selected) - created,
            would_create=0,
            dry_run=False,
        )

    def _report_progress(self, processed: int, total: int) -> None:
        if self.progress_callback is not None:
            self.progress_callback(processed, total)

    def _load_selected_profiles(
        self,
        config: JsonObject,
    ) -> dict[str, JsonObject]:
        profiles = self._read_array(
            self.bundle_root / 'data' / 'profiles.json',
        )
        codes_document = self._read_object(
            self.package_root / 'artist_codes.json',
        )
        self.codes_by_entity = {
            row['entity_id']: row['code'] for row in codes_document['artists']
        }
        selected_codes = set(config['artist_code_whitelist'])
        selected_ids = {
            entity_id
            for entity_id, code in self.codes_by_entity.items()
            if code in selected_codes
        }
        return {
            row['entity_id']: row
            for row in profiles
            if row['entity_id'] in selected_ids
        }

    def _validate_selected_relations(
        self,
        selected: dict[str, JsonObject],
    ) -> None:
        for entity_id, row in selected.items():
            parent_id = row.get('parent_label_id')
            if parent_id is None:
                continue
            if parent_id not in selected:
                raise CatalogProfileImportError(
                    'Требуемый parent_label_id находится вне whitelist; '
                    f'entity_id={entity_id}. Добавьте лейбл в whitelist '
                    'явно или исключите зависимый профиль.',
                )
            if parent_id == entity_id:
                raise CatalogProfileImportError(
                    f'Профиль ссылается на себя; entity_id={entity_id}',
                )
            if selected[parent_id].get('profile_type') != 'LABEL':
                raise CatalogProfileImportError(
                    'parent_label_id не является лейблом; '
                    f'entity_id={entity_id}',
                )

    def _validate_database_state(
        self,
        selected: dict[str, JsonObject],
    ) -> dict[str, int]:
        registry = self._get_registry()
        mappings = {
            entity_id: django_pk
            for entity_id, django_pk in registry.get_mappings(
                self.entity_type,
            ).items()
            if entity_id in selected
        }
        targets = ArtistProfile.objects.in_bulk(mappings.values())
        for entity_id, django_pk in mappings.items():
            if django_pk not in targets:
                raise CatalogProfileImportError(
                    'Реестр указывает на удалённый ArtistProfile; '
                    f'entity_id={entity_id}',
                )
            profile = targets[django_pk]
            expected_slug = self.normalize_slug(
                self._code_for_entity(entity_id),
            )
            expected_type = self._profile_type(selected[entity_id])

            if (
                profile.slug.lower() != expected_slug
                or profile.profile_type != expected_type
            ):
                raise CatalogProfileImportError(
                    'Реестр указывает на другой ArtistProfile; '
                    f'entity_id={entity_id}',
                )

        for entity_id, row in selected.items():
            if entity_id in mappings:
                continue
            slug = self.normalize_slug(self._code_for_entity(entity_id))
            if ArtistProfile.objects.filter(slug__iexact=slug).exists():
                raise CatalogProfileImportError(
                    'Slug уже занят профилем без соответствия в реестре; '
                    f'entity_id={entity_id}',
                )

        for entity_id, row in selected.items():
            parent_id = row.get('parent_label_id')
            if parent_id is None or parent_id not in mappings:
                continue
            parent = targets[mappings[parent_id]]
            if parent.profile_type != ArtistProfileType.LABEL:
                raise CatalogProfileImportError(
                    'Связанный реестр parent_label_id указывает не на '
                    f'лейбл; entity_id={entity_id}',
                )
        return mappings

    def _validate_profile_fields(
        self,
        selected: dict[str, JsonObject],
    ) -> None:
        invalid_entity_ids = []
        for entity_id, row in selected.items():
            profile = self._build_profile(row)
            try:
                profile.full_clean(
                    exclude=('label',),
                    validate_unique=False,
                    validate_constraints=False,
                )
            except ValidationError:
                invalid_entity_ids.append(entity_id)
        if invalid_entity_ids:
            joined_ids = ','.join(sorted(invalid_entity_ids))
            raise CatalogProfileImportError(
                'ArtistProfile не прошёл предварительную '
                f'Django-валидацию; entity_id={joined_ids}',
            )

    def _create_profile(self, row: JsonObject) -> bool:
        entity_id = row['entity_id']
        registry = self._get_registry()
        try:
            with transaction.atomic():
                django_pk = registry.get_mapping(self.entity_type, entity_id)
                if django_pk is not None:
                    if not ArtistProfile.objects.filter(
                        pk=django_pk,
                    ).exists():
                        raise CatalogProfileImportError(
                            'Реестр указывает на удалённый ArtistProfile; '
                            f'entity_id={entity_id}',
                        )
                    return False

                slug = self.normalize_slug(self._code_for_entity(entity_id))
                if (
                    ArtistProfile.objects
                    .select_for_update()
                    .filter(slug__iexact=slug)
                    .exists()
                ):
                    raise CatalogProfileImportError(
                        'Slug уже занят профилем без соответствующего '
                        f'реестра; entity_id={entity_id}',
                    )

                label = self._get_parent_label(row)
                profile = self._build_profile(row, label=label)
                profile.full_clean()
                profile.save()
                try:
                    registry.add_mapping(
                        self.entity_type,
                        entity_id,
                        profile.pk,
                    )
                except CatalogMigrationRegistryError as error:
                    raise CatalogProfileImportError(
                        'Не удалось записать mapping ArtistProfile; '
                        'транзакция БД отменена; '
                        f'entity_id={entity_id}',
                    ) from error
            return True
        except ValidationError as error:
            raise CatalogProfileImportError(
                'ArtistProfile не прошёл Django-валидацию; '
                f'entity_id={entity_id}',
            ) from error
        except IntegrityError as error:
            raise CatalogProfileImportError(
                f'Конфликт целостности БД; entity_id={entity_id}',
            ) from error

    def _get_parent_label(self, row: JsonObject) -> ArtistProfile | None:
        parent_id = row.get('parent_label_id')
        if parent_id is None:
            return None
        django_pk = self._get_registry().get_mapping(
            self.entity_type,
            parent_id,
        )
        if django_pk is None:
            raise CatalogProfileImportError(
                'Соответствие выбранного parent_label_id отсутствует в '
                'реестре; '
                f'entity_id={row["entity_id"]}',
            )
        parent = ArtistProfile.objects.filter(pk=django_pk).first()
        if parent is None:
            raise CatalogProfileImportError(
                'Реестр parent_label_id указывает на удалённый профиль; '
                f'entity_id={row["entity_id"]}',
            )
        if parent.profile_type != ArtistProfileType.LABEL:
            raise CatalogProfileImportError(
                'Реестр parent_label_id указывает не на лейбл; '
                f'entity_id={row["entity_id"]}',
            )
        return parent

    def _get_registry(self) -> CatalogMigrationRegistry:
        if self.registry is None:
            raise CatalogProfileImportError(
                'Реестр mappings не инициализирован.',
            )
        return self.registry

    def _build_profile(
        self,
        row: JsonObject,
        *,
        label: ArtistProfile | None = None,
    ) -> ArtistProfile:
        """Строит несохранённый профиль из проверенной строки bundle."""
        entity_id = row['entity_id']
        return ArtistProfile(
            user=None,
            label=label,
            profile_type=self._profile_type(row),
            name=row['display_name'],
            slug=self.normalize_slug(self._code_for_entity(entity_id)),
            city=row.get('city') or '',
            description=row.get('bio') or '',
            is_active=True,
        )

    def _code_for_entity(self, entity_id: str) -> str:
        return self.codes_by_entity[entity_id]

    @staticmethod
    def normalize_slug(code: str) -> str:
        """Нормализует проверенный ASCII-код в канонический lowercase slug."""
        return code.lower()

    @staticmethod
    def _profile_type(row: JsonObject) -> str:
        return (
            ArtistProfileType.LABEL
            if row['profile_type'] == 'LABEL'
            else ArtistProfileType.ARTIST
        )

    @staticmethod
    def _read_object(path: Path) -> JsonObject:
        value = CatalogProfileImporter._read_json(path)
        if not isinstance(value, dict):
            raise CatalogProfileImportError(
                f'{path.name}: ожидается JSON object после preflight',
            )
        return value

    @staticmethod
    def _read_array(path: Path) -> list[JsonObject]:
        value = CatalogProfileImporter._read_json(path)
        if not isinstance(value, list) or not all(
            isinstance(row, dict) for row in value
        ):
            raise CatalogProfileImportError(
                f'{path.name}: ожидается JSON array после preflight',
            )
        return value

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            with path.open(encoding='utf-8-sig') as source:
                return json.load(source)
        except FileNotFoundError as error:
            raise CatalogProfileImportError(
                f'{path.name}: файл исчез после preflight',
            ) from error
        except OSError as error:
            raise CatalogProfileImportError(
                f'{path.name}: ошибка чтения после preflight',
            ) from error
        except json.JSONDecodeError as error:
            raise CatalogProfileImportError(
                f'{path.name}: JSON изменён после preflight',
            ) from error
