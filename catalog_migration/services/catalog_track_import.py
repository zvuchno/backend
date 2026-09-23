"""Идемпотентный импорт метаданных Track из bundle v1.3."""

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

from store.models import Album, Track
from users.models import ArtistProfile

JsonObject = dict[str, Any]


class CatalogTrackImportError(RuntimeError):
    """Безопасная ошибка, блокирующая импорт треков."""


@dataclass(frozen=True)
class CatalogTrackImportResult:
    """Агрегированный результат импорта без содержимого треков."""

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
            f'TRACK IMPORT {mode}',
            (
                f'selected={self.selected} created={self.created} '
                f'already_mapped={self.already_mapped} '
                f'would_create={self.would_create}'
            ),
            'products=0 audio=0 uploads=0 generated_audio=0 tasks=0',
        ))


class CatalogTrackImporter:
    """Импортирует только метаданные Track и соответствующие mapping."""

    track_entity_type = 'track'
    release_entity_type = 'release'
    profile_entity_type = 'profile'

    def __init__(
        self,
        package_root: Path | str,
        *,
        dry_run: bool = False,
        track_entity_id: str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ):
        """Сохраняет путь к пакету и режим запуска."""
        self.package_root = Path(package_root).expanduser()
        self.bundle_version = bundle_version(self.package_root)
        self.mapping_version = mapping_version(self.package_root)
        self.bundle_root = bundle_root(self.package_root)
        self.dry_run = dry_run
        self.track_entity_id = track_entity_id
        self.progress_callback = progress_callback
        self.selected_releases: dict[str, JsonObject] = {}

    def run(self) -> CatalogTrackImportResult:
        """Запускает preflight и create-only импорт метаданных."""
        preflight = CatalogMigrationPreflight(self.package_root).run()
        if not preflight.passed:
            raise CatalogTrackImportError(preflight.render())

        config = self._read_object(self.package_root / 'import_config.json')
        if not config['enabled']['tracks']:
            return self._result(preflight=preflight)

        try:
            self.registry = CatalogMigrationRegistry(self.package_root)
        except CatalogMigrationRegistryError as error:
            raise CatalogTrackImportError(str(error)) from error

        selected = self._load_selected_tracks(config)
        if self.track_entity_id is not None:
            if self.track_entity_id not in selected:
                raise CatalogTrackImportError(
                    'Трек не входит в выбранный whitelist; '
                    f'entity_id={self.track_entity_id}',
                )
            selected = {
                self.track_entity_id: selected[self.track_entity_id],
            }
        album_targets = self._validate_album_mappings(selected)
        self._validate_track_fields(selected, album_targets)
        mapped = self._validate_track_mappings(selected, album_targets)
        self._validate_unmapped_track_conflicts(
            selected,
            album_targets,
            mapped,
        )
        self._report_progress(0, len(selected))

        if self.dry_run:
            return self._result(
                preflight=preflight,
                selected=len(selected),
                already_mapped=len(mapped),
                would_create=len(selected) - len(mapped),
            )

        created = 0
        for processed, entity_id in enumerate(sorted(selected), start=1):
            if entity_id in mapped:
                self._report_progress(processed, len(selected))
                continue
            if self._create_track(selected[entity_id]):
                created += 1
            self._report_progress(processed, len(selected))

        return self._result(
            preflight=preflight,
            selected=len(selected),
            created=created,
            already_mapped=len(selected) - created,
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
    ) -> CatalogTrackImportResult:
        return CatalogTrackImportResult(
            preflight=preflight,
            selected=selected,
            created=created,
            already_mapped=already_mapped,
            would_create=would_create,
            dry_run=self.dry_run,
        )

    def _load_selected_tracks(
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
        self.selected_releases = {
            row['entity_id']: row
            for row in releases
            if row['profile_id'] in selected_profile_ids
        }
        tracks = self._read_array(
            self.bundle_root / 'data' / 'tracks.json',
        )
        return {
            row['entity_id']: row
            for row in tracks
            if row['release_id'] in self.selected_releases
        }

    def _validate_album_mappings(
        self,
        selected: dict[str, JsonObject],
    ) -> dict[str, Album]:
        release_ids = {row['release_id'] for row in selected.values()}
        release_mappings = self.registry.get_mappings(
            self.release_entity_type,
        )
        release_mappings = {
            entity_id: django_pk
            for entity_id, django_pk in release_mappings.items()
            if entity_id in release_ids
        }
        albums = Album.objects.in_bulk(release_mappings.values())

        profile_ids = {
            self.selected_releases[release_id]['profile_id']
            for release_id in release_ids
        }
        profile_mappings = self.registry.get_mappings(
            self.profile_entity_type,
        )
        profile_mappings = {
            entity_id: django_pk
            for entity_id, django_pk in profile_mappings.items()
            if entity_id in profile_ids
        }
        profiles = ArtistProfile.objects.in_bulk(profile_mappings.values())

        errors = []
        for entity_id, row in selected.items():
            release_id = row['release_id']
            release_mapping = release_mappings.get(release_id)
            profile_id = self.selected_releases[release_id]['profile_id']
            profile_mapping = profile_mappings.get(profile_id)
            if release_mapping is None:
                errors.append(
                    f'Mapping Album отсутствует; entity_id={entity_id}',
                )
            elif release_mapping not in albums:
                errors.append(
                    'Mapping Album указывает на удалённый релиз; '
                    f'entity_id={entity_id}',
                )
            elif profile_mapping is None:
                errors.append(
                    'Mapping ArtistProfile отсутствует; '
                    f'entity_id={entity_id}',
                )
            elif profile_mapping not in profiles:
                errors.append(
                    'Mapping ArtistProfile указывает на удалённый профиль; '
                    f'entity_id={entity_id}',
                )
            elif albums[release_mapping].artist_id != profile_mapping:
                errors.append(
                    'Mapping Album конфликтует с mapping ArtistProfile; '
                    f'entity_id={entity_id}',
                )
        if errors:
            raise CatalogTrackImportError('\n'.join(sorted(set(errors))))
        return {
            release_id: albums[django_pk]
            for release_id, django_pk in release_mappings.items()
        }

    def _validate_track_fields(
        self,
        selected: dict[str, JsonObject],
        album_targets: dict[str, Album],
    ) -> None:
        invalid_entity_ids = []
        for entity_id, row in selected.items():
            try:
                track = self._build_track(
                    row,
                    album=album_targets[row['release_id']],
                )
                track.full_clean(validate_unique=False)
            except (TypeError, ValidationError, ValueError):
                invalid_entity_ids.append(entity_id)
        if invalid_entity_ids:
            raise CatalogTrackImportError(
                'Track не прошёл предварительную Django-валидацию; '
                f'entity_id={",".join(sorted(invalid_entity_ids))}',
            )

    def _validate_track_mappings(
        self,
        selected: dict[str, JsonObject],
        album_targets: dict[str, Album],
    ) -> dict[str, int]:
        mappings = self.registry.get_mappings(self.track_entity_type)
        mappings = {
            entity_id: django_pk
            for entity_id, django_pk in mappings.items()
            if entity_id in selected
        }
        targets = Track.objects.in_bulk(mappings.values())
        orphaned = [
            entity_id
            for entity_id, django_pk in mappings.items()
            if django_pk not in targets
        ]
        if orphaned:
            raise CatalogTrackImportError(
                'Mapping Track указывает на удалённый трек; '
                f'entity_id={",".join(sorted(orphaned))}',
            )
        conflicts = [
            entity_id
            for entity_id, django_pk in mappings.items()
            if targets[django_pk].album_id
            != album_targets[selected[entity_id]['release_id']].pk
        ]
        if conflicts:
            raise CatalogTrackImportError(
                'Mapping Track конфликтует с mapping Album; '
                f'entity_id={",".join(sorted(conflicts))}',
            )
        return mappings

    def _validate_unmapped_track_conflicts(
        self,
        selected: dict[str, JsonObject],
        album_targets: dict[str, Album],
        mapped: dict[str, int],
    ) -> None:
        candidates = {
            (
                album_targets[row['release_id']].pk,
                row['title'],
                row['position'],
            ): entity_id
            for entity_id, row in selected.items()
            if entity_id not in mapped
        }
        if not candidates:
            return
        existing = Track.objects.filter(
            album_id__in={key[0] for key in candidates},
            name__in={key[1] for key in candidates},
            position__in={key[2] for key in candidates},
        ).values_list('album_id', 'name', 'position')
        conflicts = sorted(
            candidates[key] for key in existing if key in candidates
        )
        if conflicts:
            raise CatalogTrackImportError(
                'Track уже существует без TRACK mapping; требуется '
                'ручное разрешение конфликта; '
                f'entity_id={",".join(conflicts)}',
            )

    def _create_track(self, row: JsonObject) -> bool:
        entity_id = row['entity_id']
        try:
            mapping = self.registry.get_mapping(
                self.track_entity_type,
                entity_id,
            )
            album = self._get_album_target(row)
            if mapping is not None:
                track = Track.objects.filter(pk=mapping).first()
                if track is None:
                    raise CatalogTrackImportError(
                        'Mapping Track указывает на удалённый трек; '
                        f'entity_id={entity_id}',
                    )
                if track.album_id != album.pk:
                    raise CatalogTrackImportError(
                        'Mapping Track конфликтует с mapping Album; '
                        f'entity_id={entity_id}',
                    )
                return False

            if Track.objects.filter(
                album=album,
                name=row['title'],
                position=row['position'],
            ).exists():
                raise CatalogTrackImportError(
                    'Track уже существует без TRACK mapping; требуется '
                    'ручное разрешение конфликта; '
                    f'entity_id={entity_id}',
                )
            with transaction.atomic():
                track = self._build_track(row, album=album)
                track.full_clean(validate_unique=False)
                # Обычный model.save сохраняет модельную логику Track.
                # Задачи запускают только не используемые здесь API/admin/
                # upload-сервисы; post_save receiver для Track отсутствует.
                track.save(force_insert=True)
                try:
                    self.registry.add_mapping(
                        self.track_entity_type,
                        entity_id,
                        track.pk,
                    )
                except CatalogMigrationRegistryError as error:
                    raise CatalogTrackImportError(
                        'Не удалось записать TRACK mapping; '
                        'транзакция БД отменена; '
                        f'entity_id={entity_id}',
                    ) from error
            return True
        except (TypeError, ValidationError, ValueError) as error:
            raise CatalogTrackImportError(
                f'Track не прошёл Django-валидацию; entity_id={entity_id}',
            ) from error
        except IntegrityError as error:
            raise CatalogTrackImportError(
                f'Конфликт целостности БД; entity_id={entity_id}',
            ) from error

    def _get_album_target(self, row: JsonObject) -> Album:
        release_id = row['release_id']
        release_mapping = self.registry.get_mapping(
            self.release_entity_type,
            release_id,
        )
        if release_mapping is None:
            raise CatalogTrackImportError(
                f'Mapping Album отсутствует; entity_id={row["entity_id"]}',
            )
        album = Album.objects.filter(pk=release_mapping).first()
        if album is None:
            raise CatalogTrackImportError(
                'Mapping Album указывает на удалённый релиз; '
                f'entity_id={row["entity_id"]}',
            )

        profile_id = self.selected_releases[release_id]['profile_id']
        profile_mapping = self.registry.get_mapping(
            self.profile_entity_type,
            profile_id,
        )
        if profile_mapping is None:
            raise CatalogTrackImportError(
                'Mapping ArtistProfile отсутствует; '
                f'entity_id={row["entity_id"]}',
            )
        if not ArtistProfile.objects.filter(
            pk=profile_mapping,
        ).exists():
            raise CatalogTrackImportError(
                'Mapping ArtistProfile указывает на удалённый профиль; '
                f'entity_id={row["entity_id"]}',
            )
        if album.artist_id != profile_mapping:
            raise CatalogTrackImportError(
                'Mapping Album конфликтует с mapping ArtistProfile; '
                f'entity_id={row["entity_id"]}',
            )
        return album

    @staticmethod
    def _build_track(row: JsonObject, *, album: Album) -> Track:
        """Строит несохранённый Track только с метаданными bundle."""
        return Track(
            album=album,
            name=row['title'],
            description='',
            created_by=None,
            audio_file='',
            duration=None,
            position=row['position'],
            is_active=True,
        )

    @staticmethod
    def _read_object(path: Path) -> JsonObject:
        value = CatalogTrackImporter._read_json(path)
        if not isinstance(value, dict):
            raise CatalogTrackImportError(
                f'{path.name}: ожидается JSON object после preflight',
            )
        return value

    @staticmethod
    def _read_array(path: Path) -> list[JsonObject]:
        value = CatalogTrackImporter._read_json(path)
        if not isinstance(value, list) or not all(
            isinstance(row, dict) for row in value
        ):
            raise CatalogTrackImportError(
                f'{path.name}: ожидается JSON array после preflight',
            )
        return value

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            with path.open(encoding='utf-8-sig') as file:
                return json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CatalogTrackImportError(
                f'{path.name}: не удалось прочитать JSON',
            ) from error
