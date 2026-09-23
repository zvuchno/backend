"""Минимальный реестр соответствий разовой миграции каталога."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from django.db import IntegrityError, transaction

from catalog_migration.services.catalog_bundle import mapping_version

from store.models import CatalogMigrationMapping


class CatalogMigrationRegistryError(RuntimeError):
    """Реестр содержит конфликтующее или некорректное соответствие."""


class CatalogMigrationRegistry:
    """Хранит create-only соответствия source entity в PostgreSQL."""

    def __init__(self, package_root: Path | str):
        """Определяет namespace mappings по точной версии bundle."""
        self.package_root = Path(package_root).expanduser()
        try:
            self.mapping_version = mapping_version(self.package_root)
        except OSError as error:
            raise CatalogMigrationRegistryError(
                'Не удалось прочитать bundle.json для идентификации пакета.',
            ) from error

    def get_mapping(
        self,
        entity_type: str,
        source_entity_id: str,
    ) -> int | None:
        """Возвращает сохранённый PK без изменения реестра."""
        return (
            CatalogMigrationMapping.objects
            .filter(
                bundle_version=self.mapping_version,
                entity_type=entity_type,
                source_entity_id=source_entity_id,
            )
            .values_list('django_pk', flat=True)
            .first()
        )

    def get_mappings(self, entity_type: str) -> dict[str, int]:
        """Возвращает соответствия одного типа в namespace bundle."""
        return dict(
            CatalogMigrationMapping.objects.filter(
                bundle_version=self.mapping_version,
                entity_type=entity_type,
            ).values_list('source_entity_id', 'django_pk'),
        )

    def add_mapping(
        self,
        entity_type: str,
        source_entity_id: str,
        django_pk: int,
    ) -> bool:
        """Атомарно добавляет одно соответствие."""
        return self.add_mappings({
            (entity_type, source_entity_id): django_pk,
        })

    def add_mappings(
        self,
        entries: Mapping[tuple[str, str], int],
    ) -> bool:
        """Добавляет группу соответствий без частичного результата."""
        validated = self._validate_entries(entries)
        if not validated:
            return False

        try:
            with transaction.atomic():
                entity_types = {row[0] for row in validated}
                source_ids = {row[1] for row in validated}
                django_pks = {row[2] for row in validated}
                source_mappings = {
                    (row.entity_type, row.source_entity_id): row
                    for row in (
                        CatalogMigrationMapping.objects.select_for_update().filter(
                            bundle_version=self.mapping_version,
                            entity_type__in=entity_types,
                            source_entity_id__in=source_ids,
                        )
                    )
                }
                target_mappings = {
                    (row.entity_type, row.django_pk): row
                    for row in (
                        CatalogMigrationMapping.objects.select_for_update().filter(
                            entity_type__in=entity_types,
                            django_pk__in=django_pks,
                        )
                    )
                }

                pending = []
                pending_targets: dict[tuple[str, int], str] = {}
                for entity_type, source_entity_id, django_pk in validated:
                    source_key = (entity_type, source_entity_id)
                    current = source_mappings.get(source_key)
                    if current is not None:
                        if current.django_pk != django_pk:
                            raise CatalogMigrationRegistryError(
                                'Source entity уже связан с другим Django PK; '
                                f'entity_type={entity_type}; '
                                f'entity_id={source_entity_id}',
                            )
                        continue

                    target_key = (entity_type, django_pk)
                    claimed = target_mappings.get(target_key)
                    if claimed is not None:
                        raise CatalogMigrationRegistryError(
                            'Django PK уже связан с другой source entity; '
                            f'entity_type={entity_type}; '
                            f'django_pk={django_pk}',
                        )
                    pending_source = pending_targets.get(target_key)
                    if pending_source is not None:
                        raise CatalogMigrationRegistryError(
                            'Django PK уже связан с другой source entity; '
                            f'entity_type={entity_type}; '
                            f'django_pk={django_pk}',
                        )
                    pending_targets[target_key] = source_entity_id
                    pending.append(
                        CatalogMigrationMapping(
                            bundle_version=self.mapping_version,
                            entity_type=entity_type,
                            source_entity_id=source_entity_id,
                            django_pk=django_pk,
                        ),
                    )

                if not pending:
                    return False
                CatalogMigrationMapping.objects.bulk_create(pending)
                return True
        except IntegrityError as error:
            raise CatalogMigrationRegistryError(
                'Конфликт целостности при сохранении mappings.',
            ) from error

    @staticmethod
    def _validate_entries(
        entries: Mapping[tuple[str, str], int],
    ) -> list[tuple[str, str, int]]:
        validated = []
        for key, django_pk in entries.items():
            if not isinstance(key, tuple) or len(key) != 2:
                raise CatalogMigrationRegistryError(
                    'Ключ mapping должен содержать entity_type и '
                    'source_entity_id.',
                )
            entity_type, source_entity_id = key
            if (
                not isinstance(entity_type, str)
                or not entity_type
                or not isinstance(source_entity_id, str)
                or not source_entity_id
            ):
                raise CatalogMigrationRegistryError(
                    'Тип сущности и source_entity_id не могут быть пустыми.',
                )
            if (
                not isinstance(django_pk, int)
                or isinstance(django_pk, bool)
                or django_pk <= 0
            ):
                raise CatalogMigrationRegistryError(
                    'django_pk должен быть больше 0.',
                )
            validated.append((entity_type, source_entity_id, django_pk))
        return validated
