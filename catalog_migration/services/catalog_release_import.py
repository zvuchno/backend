"""Идемпотентный импорт черновиков Album из bundle v1.3."""

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

from store.models import Album
from users.models import ArtistProfile

JsonObject = dict[str, Any]


class CatalogReleaseImportError(RuntimeError):
    """Безопасная ошибка, блокирующая импорт релизов."""


@dataclass(frozen=True)
class CatalogReleaseImportResult:
    """Агрегированный результат импорта без содержимого релизов."""

    preflight: PreflightResult
    selected: int
    created: int
    already_mapped: int
    would_create: int
    defaulted_is_single: int
    dry_run: bool

    def render(self) -> str:
        """Формирует компактный отчёт команды."""
        mode = 'DRY-RUN' if self.dry_run else 'PASS'
        return '\n'.join((
            f'RELEASE IMPORT {mode}',
            (
                f'selected={self.selected} created={self.created} '
                f'already_mapped={self.already_mapped} '
                f'would_create={self.would_create} '
                f'defaulted_is_single={self.defaulted_is_single}'
            ),
            'products=0 media=0 background_tasks=0',
        ))


class CatalogReleaseImporter:
    """Импортирует только Album и соответствующие им mapping."""

    release_entity_type = 'release'
    profile_entity_type = 'profile'

    def __init__(
        self,
        package_root: Path | str,
        *,
        dry_run: bool = False,
        release_entity_id: str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ):
        """Сохраняет путь к пакету и режим запуска."""
        self.package_root = Path(package_root).expanduser()
        self.bundle_version = bundle_version(self.package_root)
        self.mapping_version = mapping_version(self.package_root)
        self.bundle_root = bundle_root(self.package_root)
        self.dry_run = dry_run
        self.release_entity_id = release_entity_id
        self.progress_callback = progress_callback

    def run(self) -> CatalogReleaseImportResult:
        """Запускает preflight и create-only импорт релизов."""
        preflight = CatalogMigrationPreflight(self.package_root).run()
        if not preflight.passed:
            raise CatalogReleaseImportError(preflight.render())

        config = self._read_object(self.package_root / 'import_config.json')
        if not config['enabled']['releases']:
            return self._result(preflight=preflight)

        try:
            self.registry = CatalogMigrationRegistry(self.package_root)
        except CatalogMigrationRegistryError as error:
            raise CatalogReleaseImportError(str(error)) from error

        selected = self._load_selected_releases(config)
        if self.release_entity_id is not None:
            if self.release_entity_id not in selected:
                raise CatalogReleaseImportError(
                    'Релиз не входит в выбранный whitelist; '
                    f'entity_id={self.release_entity_id}',
                )
            selected = {
                self.release_entity_id: selected[self.release_entity_id],
            }
        defaulted_is_single = sum(
            row.get('is_single') is None for row in selected.values()
        )
        profile_targets = self._validate_profile_mappings(selected)
        self._validate_release_fields(selected, profile_targets)
        mapped = self._validate_release_mappings(selected, profile_targets)
        self._validate_unmapped_release_conflicts(
            selected,
            profile_targets,
            mapped,
        )
        self._report_progress(0, len(selected))

        if self.dry_run:
            return self._result(
                preflight=preflight,
                selected=len(selected),
                already_mapped=len(mapped),
                would_create=len(selected) - len(mapped),
                defaulted_is_single=defaulted_is_single,
            )

        created = 0
        for processed, entity_id in enumerate(sorted(selected), start=1):
            if entity_id in mapped:
                self._report_progress(processed, len(selected))
                continue
            if self._create_release(selected[entity_id]):
                created += 1
            self._report_progress(processed, len(selected))

        return self._result(
            preflight=preflight,
            selected=len(selected),
            created=created,
            already_mapped=len(selected) - created,
            defaulted_is_single=defaulted_is_single,
        )

    def _report_progress(self, processed: int, total: int) -> None:
        if self.progress_callback is not None:
            self.progress_callback(processed, total)

    def _result(
        self,
        *,
        preflight: PreflightResult,
        selected: int = 0,
        created: int = 0,
        already_mapped: int = 0,
        would_create: int = 0,
        defaulted_is_single: int = 0,
    ) -> CatalogReleaseImportResult:
        return CatalogReleaseImportResult(
            preflight=preflight,
            selected=selected,
            created=created,
            already_mapped=already_mapped,
            would_create=would_create,
            defaulted_is_single=defaulted_is_single,
            dry_run=self.dry_run,
        )

    def _load_selected_releases(
        self,
        config: JsonObject,
    ) -> dict[str, JsonObject]:
        codes_document = self._read_object(
            self.package_root / 'artist_codes.json',
        )
        selected_codes = set(config['artist_code_whitelist'])
        selected_profile_ids = {
            row['entity_id']
            for row in codes_document['artists']
            if row['code'] in selected_codes
        }
        releases = self._read_array(
            self.bundle_root / 'data' / 'releases.json',
        )
        return {
            row['entity_id']: row
            for row in releases
            if row['profile_id'] in selected_profile_ids
        }

    def _validate_profile_mappings(
        self,
        selected: dict[str, JsonObject],
    ) -> dict[str, ArtistProfile]:
        profile_ids = {row['profile_id'] for row in selected.values()}
        mappings = self.registry.get_mappings(self.profile_entity_type)
        mappings = {
            entity_id: django_pk
            for entity_id, django_pk in mappings.items()
            if entity_id in profile_ids
        }
        targets = ArtistProfile.objects.in_bulk(mappings.values())
        errors = []
        for entity_id, row in selected.items():
            profile_id = row['profile_id']
            mapping = mappings.get(profile_id)
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
            raise CatalogReleaseImportError('\n'.join(sorted(errors)))
        return {
            profile_id: targets[django_pk]
            for profile_id, django_pk in mappings.items()
        }

    def _validate_release_fields(
        self,
        selected: dict[str, JsonObject],
        profile_targets: dict[str, ArtistProfile],
    ) -> None:
        invalid_entity_ids = []
        for entity_id, row in selected.items():
            try:
                album = self._build_album(
                    row,
                    artist=profile_targets[row['profile_id']],
                )
                album.full_clean(validate_unique=False)
            except (TypeError, ValidationError, ValueError):
                invalid_entity_ids.append(entity_id)
        if invalid_entity_ids:
            raise CatalogReleaseImportError(
                'Album не прошёл предварительную Django-валидацию; '
                f'entity_id={",".join(sorted(invalid_entity_ids))}',
            )

    def _validate_release_mappings(
        self,
        selected: dict[str, JsonObject],
        profile_targets: dict[str, ArtistProfile],
    ) -> dict[str, int]:
        mappings = self.registry.get_mappings(self.release_entity_type)
        mappings = {
            entity_id: django_pk
            for entity_id, django_pk in mappings.items()
            if entity_id in selected
        }
        targets = Album.objects.in_bulk(mappings.values())
        orphaned = [
            entity_id
            for entity_id, django_pk in mappings.items()
            if django_pk not in targets
        ]
        if orphaned:
            raise CatalogReleaseImportError(
                'Mapping Album указывает на удалённый релиз; '
                f'entity_id={",".join(sorted(orphaned))}',
            )
        conflicts = [
            entity_id
            for entity_id, django_pk in mappings.items()
            if targets[django_pk].artist_id
            != profile_targets[selected[entity_id]['profile_id']].pk
        ]
        if conflicts:
            raise CatalogReleaseImportError(
                'Mapping Album конфликтует с mapping ArtistProfile; '
                f'entity_id={",".join(sorted(conflicts))}',
            )
        return mappings

    def _validate_unmapped_release_conflicts(
        self,
        selected: dict[str, JsonObject],
        profile_targets: dict[str, ArtistProfile],
        mapped: dict[str, int],
    ) -> None:
        candidates: dict[tuple[int, str], str] = {}

        for entity_id, row in selected.items():
            if entity_id in mapped:
                continue

            key = (profile_targets[row['profile_id']].pk, row['title'])
            previous_id = candidates.get(key)

            if previous_id is not None:
                raise CatalogReleaseImportError(
                    'Два выбранных релиза без mapping имеют одинаковое '
                    'название у одного артиста; '
                    f'entity_id={previous_id},{entity_id}',
                )

            candidates[key] = entity_id
        if not candidates:
            return
        existing = Album.objects.filter(
            artist_id__in={key[0] for key in candidates},
            name__in={key[1] for key in candidates},
        ).values_list('artist_id', 'name')
        conflicts = sorted(
            candidates[key] for key in existing if key in candidates
        )
        if conflicts:
            raise CatalogReleaseImportError(
                'Album уже существует без RELEASE mapping; требуется '
                'ручное разрешение конфликта; '
                f'entity_id={",".join(conflicts)}',
            )

    def _create_release(self, row: JsonObject) -> bool:
        entity_id = row['entity_id']
        try:
            mapping = self.registry.get_mapping(
                self.release_entity_type,
                entity_id,
            )
            if mapping is not None:
                album = Album.objects.filter(pk=mapping).first()
                if album is None:
                    raise CatalogReleaseImportError(
                        'Mapping Album указывает на удалённый релиз; '
                        f'entity_id={entity_id}',
                    )
                artist = self._get_profile_target(row)
                if album.artist_id != artist.pk:
                    raise CatalogReleaseImportError(
                        'Mapping Album конфликтует с mapping '
                        'ArtistProfile; '
                        f'entity_id={entity_id}',
                    )
                return False

            artist = self._get_profile_target(row)
            if Album.objects.filter(
                artist=artist,
                name=row['title'],
            ).exists():
                raise CatalogReleaseImportError(
                    'Album уже существует без RELEASE mapping; требуется '
                    'ручное разрешение конфликта; '
                    f'entity_id={entity_id}',
                )
            with transaction.atomic():
                album = self._build_album(row, artist=artist)
                album.full_clean(validate_unique=False)

                # bulk_create намеренно не отправляет post_save: на этом
                # этапе запрещены AlbumArchive и фоновые задачи.
                Album.objects.bulk_create([album])
                try:
                    self.registry.add_mapping(
                        self.release_entity_type,
                        entity_id,
                        album.pk,
                    )
                except CatalogMigrationRegistryError as error:
                    raise CatalogReleaseImportError(
                        'Не удалось записать RELEASE mapping; '
                        'транзакция БД отменена; '
                        f'entity_id={entity_id}',
                    ) from error
            return True
        except (TypeError, ValidationError, ValueError) as error:
            raise CatalogReleaseImportError(
                f'Album не прошёл Django-валидацию; entity_id={entity_id}',
            ) from error
        except IntegrityError as error:
            raise CatalogReleaseImportError(
                f'Конфликт целостности БД; entity_id={entity_id}',
            ) from error

    def _get_profile_target(self, row: JsonObject) -> ArtistProfile:
        mapping = self.registry.get_mapping(
            self.profile_entity_type,
            row['profile_id'],
        )
        if mapping is None:
            raise CatalogReleaseImportError(
                'Mapping ArtistProfile отсутствует; '
                f'entity_id={row["entity_id"]}',
            )
        artist = ArtistProfile.objects.filter(pk=mapping).first()
        if artist is None:
            raise CatalogReleaseImportError(
                'Mapping ArtistProfile указывает на удалённый профиль; '
                f'entity_id={row["entity_id"]}',
            )
        return artist

    @staticmethod
    def _build_album(row: JsonObject, *, artist: ArtistProfile) -> Album:
        """Строит несохранённый черновик без медиа и Product."""
        description = row.get('description')
        if description is None:
            description = ''
        if not isinstance(description, str):
            raise TypeError('description должен быть строкой или null')

        is_single = row.get('is_single')
        if is_single is None:
            # В bundle встречаются черновики с RELEASE_TYPE_REVIEW.
            # Не угадываем тип: используем технический default модели,
            # а число таких записей явно выводим в результате импорта.
            is_single = False
        elif not isinstance(is_single, bool):
            raise TypeError('is_single должен быть bool')

        return Album(
            artist=artist,
            created_by=None,
            payout_recipient=None,
            name=row['title'],
            description=description,
            release_date=row.get('release_date'),
            genre=None,
            is_single=is_single,
            cover_image=None,
            is_active=True,
            is_published=False,
        )

    @staticmethod
    def _read_object(path: Path) -> JsonObject:
        value = CatalogReleaseImporter._read_json(path)
        if not isinstance(value, dict):
            raise CatalogReleaseImportError(
                f'{path.name}: ожидается JSON object после preflight',
            )
        return value

    @staticmethod
    def _read_array(path: Path) -> list[JsonObject]:
        value = CatalogReleaseImporter._read_json(path)
        if not isinstance(value, list) or not all(
            isinstance(row, dict) for row in value
        ):
            raise CatalogReleaseImportError(
                f'{path.name}: ожидается JSON array после preflight',
            )
        return value

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            with path.open(encoding='utf-8-sig') as file:
                return json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CatalogReleaseImportError(
                f'{path.name}: не удалось прочитать JSON',
            ) from error
