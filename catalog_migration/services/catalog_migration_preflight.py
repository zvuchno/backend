"""Read-only preflight пакета разовой миграции каталога v1.3."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from jsonschema import SchemaError, validators

from catalog_migration.services.catalog_bundle import (
    bundle_root,
    bundle_version,
)

from users.constants import (
    ADDRESS_FIELD_MAX_LENGTH,
    ARTIST_LINK_LABEL_MAX_LENGTH,
    ARTIST_LINK_LABEL_MIN_LENGTH,
    CITY_FIELD_MAX_LENGTH,
    MAX_CDEK_CODE_LENGTH,
)

BUNDLE_DIRECTORY = 'zvuchno-migration-bundle-v1.3'
BUNDLE_FORMAT = 'zvuchno-catalog-migration'
BUNDLE_FORMAT_VERSION = 1
BUNDLE_VERSION = '1.3'
SCHEMA_VERSION = 1
PROFILE_COUNT = 78
CODE_PATTERN = re.compile(r'^[A-Z]{4}$')

STAGES = frozenset({
    'profiles',
    'releases',
    'tracks',
    'merch',
    'telegram',
    'cdek',
    'public_contacts',
})
CORE_DATA_FILES = {
    'profiles': 'profiles.json',
    'releases': 'releases.json',
    'tracks': 'tracks.json',
    'merch': 'merch.json',
    'variants': 'variants.json',
}
EXTRA_MANIFESTS = {
    'telegram': ('telegram_bindings.json', 'bindings'),
    'cdek': ('cdek_shipping_points.json', 'points'),
    'public_contacts': ('public_contacts.json', 'profiles'),
}
DEPENDENCIES = {
    'releases': ('profiles',),
    'tracks': ('profiles', 'releases'),
    'merch': ('profiles',),
    'telegram': ('profiles',),
    'cdek': ('profiles',),
    'public_contacts': ('profiles',),
}

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class PreflightResult:
    """Итог проверки без значений приватных полей."""

    counts: dict[str, int]
    errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Возвращает признак успешной проверки."""
        return not self.errors

    def render(self) -> str:
        """Формирует компактный безопасный для журнала отчёт."""
        lines = [f'PREFLIGHT {"PASS" if self.passed else "FAIL"}']
        lines.append(
            'COUNTS '
            + ' '.join(
                f'{name}={self.counts.get(name, 0)}'
                for name in (
                    'profiles',
                    'releases',
                    'tracks',
                    'merch',
                    'variants',
                )
            ),
        )
        for error in self.errors:
            lines.append(f'ERROR {error}')
        return '\n'.join(lines)


@dataclass
class _State:
    """Промежуточное состояние проверки."""

    errors: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        """Добавляет обезличенную ошибку."""
        self.errors.append(message)


class CatalogMigrationPreflight:
    """Проверяет локальный пакет миграции без побочных эффектов."""

    def __init__(self, package_root: Path | str):
        """Сохраняет путь к корню локального пакета."""
        self.package_root = Path(package_root).expanduser()
        self.bundle_version = bundle_version(self.package_root)
        self.bundle_root = bundle_root(self.package_root)
        self.state = _State()

    def run(self) -> PreflightResult:
        """Выполняет полную проверку пакета."""
        counts = dict.fromkeys(CORE_DATA_FILES, 0)
        if not self.package_root.is_dir():
            self.state.error('package: каталог не найден')
            return self._result(counts)
        if not self.bundle_root.is_dir():
            self.state.error(f'package: отсутствует {BUNDLE_DIRECTORY}')
            return self._result(counts)

        bundle = self._load_object(self.bundle_root / 'bundle.json')
        if bundle is None:
            return self._result(counts)
        self._validate_bundle_header(bundle)

        data = self._load_core_data(bundle)
        self._validate_bundle_schemas(bundle, data)
        profiles = data.get('profiles', [])
        profile_index = self._index_rows('profiles.json', profiles)
        self._validate_profile_rows(profiles, profile_index)

        artist_codes = self._load_object(
            self.package_root / 'artist_codes.json',
        )
        overrides = self._load_object(
            self.package_root / 'artist_slug_overrides.json',
        )
        code_to_entity = self._validate_artist_codes(
            profiles=profiles,
            profile_index=profile_index,
            document=artist_codes,
            overrides_document=overrides,
        )

        config = self._load_object(self.package_root / 'import_config.json')
        enabled, whitelist = self._validate_config(config, code_to_entity)
        self._validate_core_relations(data)
        if self.bundle_version == '2.0':
            self._validate_v2_media_and_order(bundle, data)

        selected_profiles = {
            code_to_entity[code]
            for code in whitelist
            if code in code_to_entity
        }
        counts = self._calculate_counts(data, selected_profiles, enabled)

        for stage, (filename, _) in EXTRA_MANIFESTS.items():
            if not enabled.get(stage, False):
                continue
            document = self._load_object(self.package_root / filename)
            if document is None:
                continue
            self._validate_document_version(filename, document)
            if stage == 'telegram':
                self._validate_telegram(document, profile_index)
            elif stage == 'cdek':
                self._validate_cdek(document, profile_index)
            else:
                self._validate_public_contacts(document, profile_index)

        return self._result(counts)

    def _result(self, counts: dict[str, int]) -> PreflightResult:
        return PreflightResult(counts, tuple(self.state.errors))

    def _load_json(self, path: Path) -> Any | None:
        try:
            with path.open(encoding='utf-8-sig') as source:
                return json.load(source)
        except FileNotFoundError:
            self.state.error(f'{path.name}: файл отсутствует')
        except OSError:
            self.state.error(f'{path.name}: файл недоступен для чтения')
        except json.JSONDecodeError as error:
            self.state.error(
                f'{path.name}: некорректный JSON '
                f'(строка {error.lineno}, столбец {error.colno})',
            )
        return None

    def _load_object(self, path: Path) -> JsonObject | None:
        value = self._load_json(path)
        if value is not None and not isinstance(value, dict):
            self.state.error(
                f'{path.name}: верхний уровень должен быть object',
            )
            return None
        return value

    def _validate_bundle_header(self, bundle: JsonObject) -> None:
        expected = {
            'format': BUNDLE_FORMAT,
            'format_version': BUNDLE_FORMAT_VERSION,
            'bundle_version': self.bundle_version,
        }
        for field_name, expected_value in expected.items():
            if bundle.get(field_name) != expected_value:
                self.state.error(
                    f'bundle.json: неверное поле {field_name}',
                )
        if not isinstance(bundle.get('data'), dict):
            self.state.error('bundle.json: поле data должно быть object')

    def _load_core_data(
        self,
        bundle: JsonObject,
    ) -> dict[str, list[JsonObject]]:
        result: dict[str, list[JsonObject]] = {}
        paths = bundle.get('data')
        if not isinstance(paths, dict):
            paths = {}
        for name, expected_filename in CORE_DATA_FILES.items():
            relative = paths.get(name)
            if not isinstance(relative, str):
                self.state.error(f'bundle.json: отсутствует data.{name}')
                result[name] = []
                continue
            path = (self.bundle_root / relative).resolve()
            if not path.is_relative_to(self.bundle_root.resolve()):
                self.state.error(
                    f'bundle.json: data.{name} выходит за пределы bundle',
                )
                result[name] = []
                continue
            if path.name != expected_filename:
                self.state.error(
                    f'bundle.json: неверный файл для data.{name}',
                )
            value = self._load_json(path)
            if value is None:
                result[name] = []
            elif not isinstance(value, list):
                self.state.error(
                    f'{expected_filename}: верхний уровень должен быть array',
                )
                result[name] = []
            elif not all(isinstance(row, dict) for row in value):
                self.state.error(
                    f'{expected_filename}: каждая запись должна быть object',
                )
                result[name] = [row for row in value if isinstance(row, dict)]
            else:
                result[name] = value
        self._validate_expected_counts(bundle, result)
        return result

    def _validate_expected_counts(
        self,
        bundle: JsonObject,
        data: dict[str, list[JsonObject]],
    ) -> None:
        expected = bundle.get('expected_counts')
        if not isinstance(expected, dict):
            self.state.error('bundle.json: expected_counts должен быть object')
            return
        for name, rows in data.items():
            if expected.get(name) != len(rows):
                self.state.error(
                    f'bundle.json: expected_counts.{name} не совпадает',
                )

    def _validate_bundle_schemas(
        self,
        bundle: JsonObject,
        data: dict[str, list[JsonObject]],
    ) -> None:
        schema_paths = bundle.get('schema_files')
        if not isinstance(schema_paths, dict):
            self.state.error('bundle.json: schema_files должен быть object')
            return
        documents: dict[str, Any] = {'bundle': bundle, **data}
        for name, document in documents.items():
            relative = schema_paths.get(name)
            if not isinstance(relative, str):
                self.state.error(
                    f'bundle.json: отсутствует schema_files.{name}',
                )
                continue
            path = (self.bundle_root / relative).resolve()
            if not path.is_relative_to(self.bundle_root.resolve()):
                self.state.error(
                    f'bundle.json: schema_files.{name} выходит за bundle',
                )
                continue
            schema = self._load_object(path)
            if schema is None:
                continue
            validator_class = validators.validator_for(schema)
            try:
                validator_class.check_schema(schema)
            except SchemaError:
                self.state.error(f'{path.name}: некорректная JSON Schema')
                continue
            validator = validator_class(schema)
            reported: set[str] = set()
            for error in validator.iter_errors(document):
                entity_id = self._schema_error_entity_id(document, error.path)
                message = f'{name}: данные не соответствуют JSON Schema'
                if entity_id is not None:
                    message += f'; entity_id={entity_id}'
                if message not in reported:
                    self.state.error(message)
                    reported.add(message)

    @staticmethod
    def _schema_error_entity_id(
        document: Any,
        error_path: Any,
    ) -> str | None:
        """Возвращает только безопасный идентификатор ошибочной записи."""
        path = list(error_path)
        if not path or not isinstance(path[0], int):
            return None
        index = path[0]
        if not isinstance(document, list) or index >= len(document):
            return None
        row = document[index]
        if not isinstance(row, dict):
            return None
        entity_id = row.get('entity_id')
        return entity_id if isinstance(entity_id, str) else None

    def _index_rows(
        self,
        filename: str,
        rows: list[JsonObject],
    ) -> dict[str, JsonObject]:
        result: dict[str, JsonObject] = {}
        for index, row in enumerate(rows):
            entity_id = row.get('entity_id')
            if not isinstance(entity_id, str) or not entity_id:
                self.state.error(
                    f'{filename}: запись {index} без корректного entity_id',
                )
                continue
            if entity_id in result:
                self.state.error(
                    f'{filename}: повторяющийся entity_id={entity_id}',
                )
                continue
            result[entity_id] = row
        return result

    def _validate_profile_rows(
        self,
        rows: list[JsonObject],
        profile_index: dict[str, JsonObject],
    ) -> None:
        if self.bundle_version == '1.3' and len(rows) != PROFILE_COUNT:
            self.state.error(
                f'profiles.json: ожидается {PROFILE_COUNT} профилей',
            )
        for entity_id, row in profile_index.items():
            if not isinstance(row.get('display_name'), str):
                self.state.error(
                    f'profiles.json: некорректный display_name; '
                    f'entity_id={entity_id}',
                )
            profile_type = row.get('profile_type')
            if not isinstance(profile_type, str) or profile_type not in {
                'ARTIST',
                'LABEL',
            }:
                self.state.error(
                    f'profiles.json: некорректный profile_type; '
                    f'entity_id={entity_id}',
                )
            parent_id = row.get('parent_label_id')
            if parent_id is not None and not isinstance(parent_id, str):
                self.state.error(
                    f'profiles.json: некорректный parent_label_id; '
                    f'entity_id={entity_id}',
                )
            elif parent_id is not None and parent_id not in profile_index:
                self.state.error(
                    f'profiles.json: неизвестный parent_label_id; '
                    f'entity_id={entity_id}',
                )

    def _validate_artist_codes(  # noqa: C901
        self,
        *,
        profiles: list[JsonObject],
        profile_index: dict[str, JsonObject],
        document: JsonObject | None,
        overrides_document: JsonObject | None,
    ) -> dict[str, str]:
        if document is None or overrides_document is None:
            return {}
        self._validate_document_version('artist_codes.json', document)
        if document.get('bundle_version') != self.bundle_version:
            self.state.error('artist_codes.json: неверная bundle_version')
        if overrides_document.get('schema_version') != SCHEMA_VERSION:
            self.state.error(
                'artist_slug_overrides.json: неверная schema_version',
            )

        overrides = self._index_rows(
            'artist_slug_overrides.json',
            self._object_list(
                'artist_slug_overrides.json',
                overrides_document,
                'overrides',
            ),
        )
        artists = self._object_list(
            'artist_codes.json',
            document,
            'artists',
        )
        artist_index = self._index_rows('artist_codes.json', artists)

        expected_profiles = (
            PROFILE_COUNT if self.bundle_version == '1.3' else len(profiles)
        )
        if len(artists) != expected_profiles:
            self.state.error(
                'artist_codes.json: ожидается '
                f'{expected_profiles} соответствий',
            )
        if set(artist_index) != set(profile_index):
            self.state.error(
                'artist_codes.json: набор entity_id не совпадает '
                'с profiles.json',
            )

        code_to_entity: dict[str, str] = {}
        for entity_id, row in artist_index.items():
            code = row.get('code')
            provenance = row.get('provenance')
            if not isinstance(code, str) or not CODE_PATTERN.fullmatch(code):
                self.state.error(
                    f'artist_codes.json: код не соответствует [A-Z]{{4}}; '
                    f'entity_id={entity_id}',
                )
                continue
            if code in code_to_entity:
                self.state.error(
                    f'artist_codes.json: повторяющийся code; '
                    f'entity_id={entity_id}',
                )
            else:
                code_to_entity[code] = entity_id

            profile = profile_index.get(entity_id)
            if profile is None:
                continue
            preferred = profile.get('preferred_legacy_id')
            override = overrides.get(entity_id)
            if preferred is not None:
                if code != preferred or provenance != (
                    'bundle_preferred_legacy_id'
                ):
                    self.state.error(
                        'artist_codes.json: код или provenance не совпадает '
                        f'с preferred_legacy_id; entity_id={entity_id}',
                    )
                if override is not None:
                    self.state.error(
                        'artist_slug_overrides.json: лишний override; '
                        f'entity_id={entity_id}',
                    )
            elif override is None:
                self.state.error(
                    'artist_slug_overrides.json: отсутствует override; '
                    f'entity_id={entity_id}',
                )
            elif (
                override.get('slug') != code
                or override.get('provenance') != provenance
            ):
                self.state.error(
                    'artist_codes.json: код или provenance не совпадает '
                    f'с override; entity_id={entity_id}',
                )
            elif provenance not in {
                'assigned',
                'telegram_export_confirmed',
            }:
                self.state.error(
                    'artist_codes.json: неизвестное происхождение override; '
                    f'entity_id={entity_id}',
                )

        missing_preferred = {
            row.get('entity_id')
            for row in profiles
            if row.get('preferred_legacy_id') is None
            and isinstance(row.get('entity_id'), str)
        }
        if set(overrides) != missing_preferred:
            self.state.error(
                'artist_slug_overrides.json: набор entity_id не совпадает '
                'с профилями без preferred_legacy_id',
            )
        return code_to_entity

    def _validate_config(  # noqa: C901
        self,
        config: JsonObject | None,
        code_to_entity: dict[str, str],
    ) -> tuple[dict[str, bool], list[str]]:
        if config is None:
            return {}, []
        self._validate_document_version('import_config.json', config)
        enabled_value = config.get('enabled')
        if not isinstance(enabled_value, dict):
            self.state.error('import_config.json: enabled должен быть object')
            enabled: dict[str, bool] = {}
        else:
            enabled = {
                name: value
                for name, value in enabled_value.items()
                if isinstance(value, bool)
            }
            if set(enabled_value) != STAGES:
                self.state.error(
                    'import_config.json: требуется ровно семь переключателей',
                )
            for name in STAGES:
                if not isinstance(enabled_value.get(name), bool):
                    self.state.error(
                        f'import_config.json: enabled.{name} должен быть bool',
                    )

        for stage, requirements in DEPENDENCIES.items():
            if not enabled.get(stage, False):
                continue
            for requirement in requirements:
                if not enabled.get(requirement, False):
                    self.state.error(
                        f'import_config.json: этап {stage} требует '
                        f'включённый этап {requirement}',
                    )

        whitelist_value = config.get('artist_code_whitelist')
        if not isinstance(whitelist_value, list) or not all(
            isinstance(code, str) for code in whitelist_value
        ):
            self.state.error(
                'import_config.json: artist_code_whitelist должен быть '
                'array строк',
            )
            return enabled, []
        whitelist = whitelist_value
        duplicates = {
            code for code, count in Counter(whitelist).items() if count > 1
        }
        for code in sorted(duplicates):
            self.state.error(
                f'import_config.json: повторяющийся код {code}',
            )
        for code in sorted(set(whitelist) - set(code_to_entity)):
            self.state.error(f'import_config.json: неизвестный код {code}')
        return enabled, whitelist

    def _validate_core_relations(
        self,
        data: dict[str, list[JsonObject]],
    ) -> None:
        indexes = {
            name: self._index_rows(f'{name}.json', rows)
            for name, rows in data.items()
        }
        profile_ids = set(indexes['profiles'])
        release_ids = set(indexes['releases'])
        merch_ids = set(indexes['merch'])

        self._validate_references(
            'releases.json',
            indexes['releases'],
            'profile_id',
            profile_ids,
        )
        self._validate_references(
            'tracks.json',
            indexes['tracks'],
            'release_id',
            release_ids,
        )
        self._validate_references(
            'merch.json',
            indexes['merch'],
            'profile_id',
            profile_ids,
        )
        self._validate_references(
            'merch.json',
            indexes['merch'],
            'release_id',
            release_ids,
            nullable=True,
        )
        self._validate_references(
            'variants.json',
            indexes['variants'],
            'merch_id',
            merch_ids,
        )

    def _validate_references(
        self,
        filename: str,
        rows: dict[str, JsonObject],
        field_name: str,
        targets: set[str],
        *,
        nullable: bool = False,
    ) -> None:
        for entity_id, row in rows.items():
            reference = row.get(field_name)
            if nullable and reference is None:
                continue
            if not isinstance(reference, str) or reference not in targets:
                self.state.error(
                    f'{filename}: битая ссылка {field_name}; '
                    f'entity_id={entity_id}',
                )

    def _calculate_counts(
        self,
        data: dict[str, list[JsonObject]],
        profile_ids: set[str],
        enabled: dict[str, bool],
    ) -> dict[str, int]:
        releases = {
            row['entity_id']
            for row in data['releases']
            if isinstance(row.get('profile_id'), str)
            and row.get('profile_id') in profile_ids
            and isinstance(row.get('entity_id'), str)
        }
        tracks = [
            row
            for row in data['tracks']
            if isinstance(row.get('release_id'), str)
            and row.get('release_id') in releases
        ]
        merch = {
            row['entity_id']
            for row in data['merch']
            if isinstance(row.get('profile_id'), str)
            and row.get('profile_id') in profile_ids
            and isinstance(row.get('entity_id'), str)
        }
        variants = [
            row
            for row in data['variants']
            if isinstance(row.get('merch_id'), str)
            and row.get('merch_id') in merch
        ]
        return {
            'profiles': len(profile_ids) if enabled.get('profiles') else 0,
            'releases': len(releases) if enabled.get('releases') else 0,
            'tracks': len(tracks) if enabled.get('tracks') else 0,
            'merch': len(merch) if enabled.get('merch') else 0,
            'variants': len(variants) if enabled.get('merch') else 0,
        }

    def _validate_telegram(
        self,
        document: JsonObject,
        profile_index: dict[str, JsonObject],
    ) -> None:
        rows = self._object_list(
            'telegram_bindings.json',
            document,
            'bindings',
        )
        index = self._index_rows('telegram_bindings.json', rows)
        chats: dict[int, str] = {}
        for entity_id, row in index.items():
            self._validate_profile_reference(
                'telegram_bindings.json',
                entity_id,
                profile_index,
            )
            chat_id = row.get('chat_id')
            if (
                not isinstance(chat_id, int)
                or isinstance(chat_id, bool)
                or not -(2**63) <= chat_id < 2**63
            ):
                self.state.error(
                    'telegram_bindings.json: некорректный chat_id; '
                    f'entity_id={entity_id}',
                )
            elif chat_id in chats and chats[chat_id] != entity_id:
                self.state.error(
                    'telegram_bindings.json: повторяющийся chat_id; '
                    f'entity_id={chats[chat_id]},{entity_id}',
                )
            else:
                chats[chat_id] = entity_id
            if not isinstance(row.get('matched_in_both_sources'), bool):
                self.state.error(
                    'telegram_bindings.json: некорректный '
                    f'matched_in_both_sources; entity_id={entity_id}',
                )
            sources_match = row.get('sources_match')
            if sources_match is not None and not isinstance(
                sources_match,
                bool,
            ):
                self.state.error(
                    'telegram_bindings.json: некорректный sources_match; '
                    f'entity_id={entity_id}',
                )

    def _validate_cdek(
        self,
        document: JsonObject,
        profile_index: dict[str, JsonObject],
    ) -> None:
        rows = self._object_list(
            'cdek_shipping_points.json',
            document,
            'points',
        )
        index = self._index_rows('cdek_shipping_points.json', rows)
        pvz_codes: set[str] = set()
        for entity_id, row in index.items():
            self._validate_profile_reference(
                'cdek_shipping_points.json',
                entity_id,
                profile_index,
            )
            self._validate_bounded_string(
                'cdek_shipping_points.json',
                entity_id,
                row,
                'pvz_code',
                MAX_CDEK_CODE_LENGTH,
            )
            self._validate_bounded_string(
                'cdek_shipping_points.json',
                entity_id,
                row,
                'city_code',
                MAX_CDEK_CODE_LENGTH,
            )
            self._validate_bounded_string(
                'cdek_shipping_points.json',
                entity_id,
                row,
                'pvz_city',
                CITY_FIELD_MAX_LENGTH,
            )
            self._validate_bounded_string(
                'cdek_shipping_points.json',
                entity_id,
                row,
                'address',
                ADDRESS_FIELD_MAX_LENGTH,
            )
            pvz_code = row.get('pvz_code')
            if isinstance(pvz_code, str):
                if pvz_code in pvz_codes:
                    self.state.error(
                        'cdek_shipping_points.json: повторяющийся pvz_code; '
                        f'entity_id={entity_id}',
                    )
                pvz_codes.add(pvz_code)
            if row.get('status') != 'pending_api':
                self.state.error(
                    'cdek_shipping_points.json: status должен быть '
                    f'pending_api; entity_id={entity_id}',
                )
            missing = row.get('missing_fields')
            if not isinstance(missing, list) or not all(
                isinstance(item, str) for item in missing
            ):
                self.state.error(
                    'cdek_shipping_points.json: некорректный '
                    f'missing_fields; entity_id={entity_id}',
                )

    def _validate_public_contacts(
        self,
        document: JsonObject,
        profile_index: dict[str, JsonObject],
    ) -> None:
        rows = self._object_list(
            'public_contacts.json',
            document,
            'profiles',
        )
        index = self._index_rows('public_contacts.json', rows)
        for entity_id, row in index.items():
            self._validate_profile_reference(
                'public_contacts.json',
                entity_id,
                profile_index,
            )
            self._validate_contact_items(
                entity_id,
                row.get('contacts'),
                'contacts',
                validate_email,
            )
            self._validate_contact_items(
                entity_id,
                row.get('socials'),
                'socials',
                URLValidator(),
            )
        manual_review = document.get('manual_review')
        if not isinstance(manual_review, list):
            self.state.error(
                'public_contacts.json: manual_review должен быть array',
            )
            return
        for index_number, item in enumerate(manual_review):
            if not isinstance(item, dict):
                self.state.error(
                    'public_contacts.json: некорректная запись '
                    f'manual_review[{index_number}]',
                )
                continue
            entity_ids = item.get('entity_ids')
            if not isinstance(entity_ids, list):
                self.state.error(
                    'public_contacts.json: некорректные entity_ids в '
                    f'manual_review[{index_number}]',
                )
                continue
            for entity_id in entity_ids:
                if not isinstance(entity_id, str):
                    self.state.error(
                        'public_contacts.json: некорректный entity_id в '
                        f'manual_review[{index_number}]',
                    )
                elif entity_id not in profile_index:
                    self.state.error(
                        'public_contacts.json: неизвестный entity_id в '
                        f'manual_review[{index_number}]',
                    )

    def _validate_contact_items(
        self,
        entity_id: str,
        value: Any,
        field_name: str,
        value_validator: Any,
    ) -> None:
        if not isinstance(value, list):
            self.state.error(
                f'public_contacts.json: {field_name} должен быть array; '
                f'entity_id={entity_id}',
            )
            return
        seen: set[tuple[str, str]] = set()
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                self.state.error(
                    'public_contacts.json: некорректный '
                    f'{field_name}[{index}]; '
                    f'entity_id={entity_id}',
                )
                continue
            label = item.get('label')
            item_value = item.get('value')
            if (
                not isinstance(label, str)
                or not ARTIST_LINK_LABEL_MIN_LENGTH
                <= len(label)
                <= ARTIST_LINK_LABEL_MAX_LENGTH
            ):
                self.state.error(
                    f'public_contacts.json: некорректный label в '
                    f'{field_name}[{index}]; entity_id={entity_id}',
                )
            if not isinstance(item_value, str):
                self.state.error(
                    f'public_contacts.json: некорректный value в '
                    f'{field_name}[{index}]; entity_id={entity_id}',
                )
                continue
            try:
                value_validator(item_value)
            except ValidationError:
                self.state.error(
                    f'public_contacts.json: value не проходит Django '
                    f'валидацию в {field_name}[{index}]; '
                    f'entity_id={entity_id}',
                )
            if isinstance(label, str):
                pair = (label, item_value)
                if pair in seen:
                    self.state.error(
                        f'public_contacts.json: дубль label/value в '
                        f'{field_name}; entity_id={entity_id}',
                    )
                seen.add(pair)

    def _validate_profile_reference(
        self,
        filename: str,
        entity_id: str,
        profile_index: dict[str, JsonObject],
    ) -> None:
        if entity_id not in profile_index:
            self.state.error(
                f'{filename}: неизвестный entity_id={entity_id}',
            )

    def _validate_bounded_string(
        self,
        filename: str,
        entity_id: str,
        row: JsonObject,
        field_name: str,
        max_length: int,
    ) -> None:
        value = row.get(field_name)
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > max_length
        ):
            self.state.error(
                f'{filename}: некорректный {field_name}; '
                f'entity_id={entity_id}',
            )

    def _validate_document_version(
        self,
        filename: str,
        document: JsonObject,
    ) -> None:
        if document.get('schema_version') != SCHEMA_VERSION:
            self.state.error(f'{filename}: неверная schema_version')
        if document.get('bundle_version') != self.bundle_version:
            self.state.error(f'{filename}: неверная bundle_version')

    def _object_list(
        self,
        filename: str,
        document: JsonObject,
        field_name: str,
    ) -> list[JsonObject]:
        value = document.get(field_name)
        if not isinstance(value, list):
            self.state.error(
                f'{filename}: {field_name} должен быть array',
            )
            return []
        if not all(isinstance(item, dict) for item in value):
            self.state.error(
                f'{filename}: элементы {field_name} должны быть object',
            )
            return [item for item in value if isinstance(item, dict)]
        return value

    def _validate_v2_media_and_order(  # noqa: C901
        self,
        bundle,
        data,
    ) -> None:
        """Validate explicit order and media without a gallery-size cap."""
        import hashlib
        from collections import defaultdict

        for relative, expected in bundle.get('content_sha256', {}).items():
            path = (self.bundle_root / relative).resolve()
            if not path.is_relative_to(self.bundle_root.resolve()):
                self.state.error('v2: unsafe content checksum path')
            elif (
                not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected
            ):
                self.state.error(f'v2: content checksum mismatch: {relative}')
        positions = defaultdict(list)
        for track in data.get('tracks', []):
            positions[track.get('release_id')].append(track.get('position'))
            if track.get('order_confirmed') is not True:
                self.state.error(
                    'v2: track order must come from release_tracks.csv',
                )
        for release in data.get('releases', []):
            values = positions[release['entity_id']]
            if (
                not all(type(v) is int for v in values)
                or sorted(values) != list(range(1, len(values) + 1))
                or len(values) != release.get('expected_track_count')
            ):
                self.state.error(
                    'v2: invalid track positions/count; '
                    f'entity_id={release["entity_id"]}',
                )
        for kind in ('audio', 'images'):
            document = self._load_object(
                self.bundle_root / 'media' / 'manifests' / (kind + '.json'),
            )
            if document is None:
                continue
            assets = document.get('assets', [])
            index = {}
            paths = set()
            for asset in assets:
                aid = asset.get('asset_id')
                if not isinstance(aid, str) or aid in index:
                    self.state.error('v2: duplicate/invalid media ID')
                index[aid] = asset
                relative = asset.get('bundle_path', '')
                path = (self.bundle_root / relative).resolve()
                if (
                    not relative.startswith(
                        'media/'
                        + (
                            'audio/originals/'
                            if kind == 'audio'
                            else 'images/'
                        ),
                    )
                    or '..' in Path(relative).parts
                    or not path.is_relative_to(self.bundle_root.resolve())
                    or relative in paths
                ):
                    self.state.error('v2: invalid/duplicate media path')
                    continue
                paths.add(relative)
                digest = asset.get('sha256', '')
                if not isinstance(digest, str) or not re.fullmatch(
                    '[0-9a-f]{64}',
                    digest,
                ):
                    self.state.error('v2: invalid media SHA256')
                if not settings.USE_S3_MEDIA and (
                    not path.is_file()
                    or path.stat().st_size != asset.get('size')
                ):
                    self.state.error(
                        'v2: missing or wrong-sized delivered media; '
                        f'asset_id={aid}',
                    )
                if kind == 'images' and (
                    asset.get('format') not in {'JPEG', 'PNG', 'WEBP'}
                    or not 0 < asset.get('size', 0) <= 10 * 1024 * 1024
                ):
                    self.state.error('v2: invalid image format/size')
            expected = bundle['expected_counts'].get(
                'expected_audio_assets' if kind == 'audio' else 'images',
            )
            if len(assets) != expected:
                self.state.error('v2: media count mismatch')
            referenced = []
            if kind == 'audio':
                for track in data.get('tracks', []):
                    aid = track.get('audio_asset_id')
                    if aid is None and track.get('audio_status') == 'MISSING':
                        continue
                    referenced.append(aid)
                    if (
                        aid not in index
                        or index[aid].get('entity_id') != track['entity_id']
                    ):
                        self.state.error('v2: broken track audio reference')
            else:
                for dataset, entity_type in [
                    ('profiles', 'profile'),
                    ('releases', 'release'),
                    ('merch', 'merch'),
                ]:
                    for row in data.get(dataset, []):
                        ids = row.get('image_asset_ids', [])
                        referenced.extend(ids)
                        actual = [
                            a['asset_id']
                            for a in assets
                            if a.get('entity_id') == row['entity_id']
                            and a.get('entity_type') == entity_type
                        ]
                        if ids != actual:
                            self.state.error(
                                'v2: broken image references/order',
                            )
            if len(referenced) != len(set(referenced)) or set(
                referenced,
            ) != set(index):
                self.state.error('v2: orphan/duplicate media assignment')
