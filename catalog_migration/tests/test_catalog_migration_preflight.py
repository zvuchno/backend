"""Тесты read-only preflight пакета миграции каталога."""

import json
from pathlib import Path

import pytest

from catalog_migration.services.catalog_migration_preflight import (
    BUNDLE_DIRECTORY,
    CatalogMigrationPreflight,
)


def _code(index: int) -> str:
    """Формирует уникальный четырёхбуквенный код."""
    letters = []
    for _ in range(4):
        letters.append(chr(ord('A') + index % 26))
        index //= 26
    return ''.join(reversed(letters))


def _write_json(path: Path, value: object) -> None:
    """Записывает JSON тестового пакета."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False),
        encoding='utf-8',
    )


def _make_package(tmp_path: Path) -> Path:  # noqa: C901
    """Создаёт минимальный валидный пакет с 78 профилями."""
    package = tmp_path / 'migration-v1.3'
    bundle = package / BUNDLE_DIRECTORY
    data_directory = bundle / 'data'
    schema_directory = bundle / 'schema'

    profiles = []
    artist_codes = []
    overrides = []
    for index in range(78):
        entity_id = f'profile-{index:02d}'
        code = _code(index)
        preferred = code if index < 54 else None
        profiles.append({
            'entity_id': entity_id,
            'display_name': f'Profile {index}',
            'profile_type': 'ARTIST',
            'parent_label_id': None,
            'bio': None,
            'status': 'DRAFT',
            'account_merge_authorized': False,
            'preferred_legacy_id': preferred,
        })
        provenance = 'bundle_preferred_legacy_id' if preferred else 'assigned'
        artist_codes.append({
            'entity_id': entity_id,
            'code': code,
            'provenance': provenance,
        })
        if preferred is None:
            overrides.append({
                'entity_id': entity_id,
                'slug': code,
                'provenance': provenance,
            })

    releases = [
        {
            'entity_id': f'release-{index:02d}',
            'profile_id': f'profile-{index:02d}',
            'title': f'Release {index}',
            'status': 'DRAFT',
            'source_price': None,
            'target_price': None,
            'expected_track_count': 1,
        }
        for index in range(3)
    ]
    tracks = [
        {
            'entity_id': f'track-{index:02d}',
            'release_id': f'release-{index:02d}',
            'position': 1,
            'title': f'Track {index}',
            'audio_asset_id': f'audio-{index:02d}',
            'status': 'DRAFT',
        }
        for index in range(3)
    ]
    merch = [
        {
            'entity_id': f'merch-{index:02d}',
            'profile_id': f'profile-{index:02d}',
            'release_id': f'release-{index:02d}',
            'title': f'Merch {index}',
            'status': 'DRAFT',
            'source_price': None,
            'target_price': None,
        }
        for index in range(3)
    ]
    variants = [
        {
            'entity_id': f'variant-{index:02d}',
            'merch_id': f'merch-{index:02d}',
            'status': 'DRAFT',
            'source_stock': 1,
            'target_stock': 1,
            'final_sku': None,
            'sku_strategy': 'BACKEND_GENERATED',
        }
        for index in range(3)
    ]
    core_data = {
        'profiles': profiles,
        'releases': releases,
        'tracks': tracks,
        'merch': merch,
        'variants': variants,
    }
    for name, rows in core_data.items():
        _write_json(data_directory / f'{name}.json', rows)

    schema_files = {'bundle': 'schema/bundle.schema.json'}
    _write_json(
        schema_directory / 'bundle.schema.json',
        {'type': 'object'},
    )
    for name in core_data:
        schema_files[name] = f'schema/{name}.schema.json'
        _write_json(
            schema_directory / f'{name}.schema.json',
            {'type': 'array', 'items': {'type': 'object'}},
        )

    _write_json(
        bundle / 'bundle.json',
        {
            'format': 'zvuchno-catalog-migration',
            'format_version': 1,
            'bundle_version': '1.3',
            'data': {name: f'data/{name}.json' for name in core_data},
            'schema_files': schema_files,
            'expected_counts': {
                name: len(rows) for name, rows in core_data.items()
            },
        },
    )
    _write_json(
        package / 'artist_codes.json',
        {
            'schema_version': 1,
            'bundle_version': '1.3',
            'artists': artist_codes,
        },
    )
    _write_json(
        package / 'artist_slug_overrides.json',
        {
            'schema_version': 1,
            'overrides': overrides,
        },
    )
    _write_json(
        package / 'import_config.json',
        {
            'schema_version': 1,
            'bundle_version': '1.3',
            'enabled': {
                'profiles': True,
                'releases': True,
                'tracks': True,
                'merch': True,
                'telegram': True,
                'cdek': True,
                'public_contacts': True,
            },
            'artist_code_whitelist': [item['code'] for item in artist_codes],
        },
    )
    _write_json(
        package / 'telegram_bindings.json',
        {
            'schema_version': 1,
            'bundle_version': '1.3',
            'bindings': [
                {
                    'entity_id': 'profile-00',
                    'chat_id': 100,
                    'matched_in_both_sources': True,
                    'sources_match': True,
                },
            ],
        },
    )
    _write_json(
        package / 'cdek_shipping_points.json',
        {
            'schema_version': 1,
            'bundle_version': '1.3',
            'points': [
                {
                    'entity_id': 'profile-00',
                    'pvz_code': 'MSK1',
                    'city_code': '44',
                    'pvz_city': 'Москва',
                    'address': 'Москва',
                    'status': 'pending_api',
                    'missing_fields': [],
                },
            ],
        },
    )
    _write_json(
        package / 'public_contacts.json',
        {
            'schema_version': 1,
            'bundle_version': '1.3',
            'profiles': [
                {
                    'entity_id': 'profile-00',
                    'contacts': [
                        {
                            'label': 'Email',
                            'value': 'public@example.com',
                        },
                    ],
                    'socials': [
                        {
                            'label': 'Website',
                            'value': 'https://example.com',
                        },
                    ],
                },
            ],
            'manual_review': [
                {
                    'entity_ids': ['profile-00'],
                },
            ],
        },
    )
    return package


def _load(path: Path) -> dict:
    """Читает изменяемый JSON тестового пакета."""
    return json.loads(path.read_text(encoding='utf-8'))


def _replace_row_field(
    package: Path,
    relative_path: str,
    list_field: str | None,
    field_name: str,
    value: object,
) -> None:
    """Подменяет одно поле записи в синтетической ведомости."""
    path = package / relative_path
    document = _load(path)
    rows = document[list_field] if list_field is not None else document
    rows[0][field_name] = value
    _write_json(path, document)


def test_empty_whitelist_means_zero_import(tmp_path):
    """Пустой whitelist даёт нулевой план импорта."""
    package = _make_package(tmp_path)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    config['artist_code_whitelist'] = []
    _write_json(config_path, config)

    result = CatalogMigrationPreflight(package).run()

    assert result.passed
    assert result.counts == {
        'profiles': 0,
        'releases': 0,
        'tracks': 0,
        'merch': 0,
        'variants': 0,
    }


def test_whitelist_filters_all_catalog_relations(tmp_path):
    """Дочерние сущности выбираются через связи двух профилей."""
    package = _make_package(tmp_path)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    config['artist_code_whitelist'] = [_code(0), _code(1)]
    _write_json(config_path, config)

    result = CatalogMigrationPreflight(package).run()

    assert result.passed
    assert result.counts == {
        'profiles': 2,
        'releases': 2,
        'tracks': 2,
        'merch': 2,
        'variants': 2,
    }


def test_disabled_tracks_and_merch_have_zero_counts(tmp_path):
    """Отключённые этапы сохраняют нулевые плановые количества."""
    package = _make_package(tmp_path)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    config['enabled']['tracks'] = False
    config['enabled']['merch'] = False
    _write_json(config_path, config)

    result = CatalogMigrationPreflight(package).run()

    assert result.passed
    assert result.counts == {
        'profiles': 78,
        'releases': 3,
        'tracks': 0,
        'merch': 0,
        'variants': 0,
    }


def test_unknown_whitelist_code_is_error(tmp_path):
    """Неизвестный код отклоняется."""
    package = _make_package(tmp_path)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    config['artist_code_whitelist'].append('ZZZZ')
    _write_json(config_path, config)

    result = CatalogMigrationPreflight(package).run()

    assert not result.passed
    assert any('неизвестный код ZZZZ' in error for error in result.errors)


def test_broken_bundle_reference_is_error(tmp_path):
    """Битая дочерняя ссылка обнаруживается по entity_id."""
    package = _make_package(tmp_path)
    releases_path = package / BUNDLE_DIRECTORY / 'data' / 'releases.json'
    releases = _load(releases_path)
    releases[0]['profile_id'] = 'missing-profile'
    _write_json(releases_path, releases)

    result = CatalogMigrationPreflight(package).run()

    assert not result.passed
    assert any(
        'битая ссылка profile_id; entity_id=release-00' in error
        for error in result.errors
    )


def test_missing_enabled_manifest_is_error(tmp_path):
    """Отсутствующая ведомость включённого этапа блокирует preflight."""
    package = _make_package(tmp_path)
    (package / 'telegram_bindings.json').unlink()

    result = CatalogMigrationPreflight(package).run()

    assert not result.passed
    assert 'telegram_bindings.json: файл отсутствует' in result.errors


def test_missing_artist_row_in_extra_manifest_is_allowed(tmp_path):
    """Дополнительная ведомость может не содержать отдельного артиста."""
    package = _make_package(tmp_path)

    result = CatalogMigrationPreflight(package).run()

    assert result.passed


def test_duplicate_chat_id_for_different_profiles_is_error(tmp_path):
    """Один chat_id нельзя связать с двумя профилями."""
    package = _make_package(tmp_path)
    telegram_path = package / 'telegram_bindings.json'
    telegram = _load(telegram_path)
    telegram['bindings'].append({
        'entity_id': 'profile-01',
        'chat_id': 100,
        'matched_in_both_sources': False,
        'sources_match': None,
    })
    _write_json(telegram_path, telegram)

    result = CatalogMigrationPreflight(package).run()

    assert not result.passed
    assert any(
        'повторяющийся chat_id; entity_id=profile-00,profile-01' in error
        for error in result.errors
    )


@pytest.mark.parametrize(
    ('relative_path', 'list_field', 'field_name', 'bad_value', 'error_text'),
    [
        (
            'telegram_bindings.json',
            'bindings',
            'sources_match',
            {},
            'некорректный sources_match',
        ),
        (
            f'{BUNDLE_DIRECTORY}/data/profiles.json',
            None,
            'parent_label_id',
            [],
            'некорректный parent_label_id',
        ),
        (
            f'{BUNDLE_DIRECTORY}/data/releases.json',
            None,
            'profile_id',
            [],
            'битая ссылка profile_id',
        ),
        (
            f'{BUNDLE_DIRECTORY}/data/tracks.json',
            None,
            'release_id',
            {},
            'битая ссылка release_id',
        ),
        (
            f'{BUNDLE_DIRECTORY}/data/merch.json',
            None,
            'profile_id',
            [],
            'битая ссылка profile_id',
        ),
        (
            f'{BUNDLE_DIRECTORY}/data/variants.json',
            None,
            'merch_id',
            {},
            'битая ссылка merch_id',
        ),
        (
            'public_contacts.json',
            'manual_review',
            'entity_ids',
            [[]],
            'некорректный entity_id в manual_review[0]',
        ),
    ],
)
def test_invalid_reference_types_return_fail_without_exception(
    tmp_path,
    relative_path,
    list_field,
    field_name,
    bad_value,
    error_text,
):
    """Нехешируемые JSON-значения дают FAIL вместо traceback."""
    package = _make_package(tmp_path)
    _replace_row_field(
        package,
        relative_path,
        list_field,
        field_name,
        bad_value,
    )

    result = CatalogMigrationPreflight(package).run()

    assert not result.passed
    assert result.render().startswith('PREFLIGHT FAIL\n')
    assert any(error_text in error for error in result.errors)
