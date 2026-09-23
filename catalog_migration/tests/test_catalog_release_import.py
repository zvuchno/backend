"""Тесты разового импорта Album из bundle v1.3."""

from io import StringIO
from typing import Never

import pytest
from django.core.management import call_command

from catalog_migration.services.catalog_migration_preflight import (
    BUNDLE_DIRECTORY,
)
from catalog_migration.services.catalog_migration_registry import (
    CatalogMigrationRegistry,
    CatalogMigrationRegistryError,
)
from catalog_migration.services.catalog_release_import import (
    CatalogReleaseImportError,
    CatalogReleaseImporter,
)
from catalog_migration.tests.test_catalog_migration_preflight import (
    _code,
    _load,
    _make_package,
    _write_json,
)

from store.models import (
    Album,
    AlbumArchive,
    CatalogMigrationMapping,
    Product,
)
from users.models import ArtistProfile


def _set_whitelist(package, *profile_indexes: int) -> None:
    path = package / 'import_config.json'
    config = _load(path)
    config['artist_code_whitelist'] = [
        _code(index) for index in profile_indexes
    ]
    _write_json(path, config)


def _create_profile_mapping(package, index: int) -> ArtistProfile:
    profile = ArtistProfile.objects.create(
        name=f'Profile {index}',
        slug=_code(index).lower(),
    )
    CatalogMigrationRegistry(package).add_mapping(
        'profile',
        f'profile-{index:02d}',
        profile.pk,
    )
    return profile


@pytest.mark.django_db
def test_first_import_creates_draft_album_and_mapping_without_side_effects(
    tmp_path,
    monkeypatch,
):
    """Первый запуск создаёт только черновик Album и mapping."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    artist = _create_profile_mapping(package, 0)
    schedule_calls = []
    monkeypatch.setattr(
        'store.services.album_archive.AlbumArchiveScheduler.schedule_by_id',
        schedule_calls.append,
    )

    result = CatalogReleaseImporter(package).run()

    assert result.selected == 1
    assert result.created == 1
    assert result.already_mapped == 0
    album = Album.objects.get()
    assert album.artist == artist
    assert album.name == 'Release 0'
    assert album.description == ''
    assert album.created_by_id is None
    assert album.payout_recipient_id is None
    assert album.is_active is True
    assert album.is_published is False
    assert not album.cover_image
    mapping = CatalogMigrationRegistry(package).get_mapping(
        'release',
        'release-00',
    )
    assert mapping == album.pk
    assert Product.objects.count() == 0
    assert AlbumArchive.objects.count() == 0
    assert CatalogMigrationMapping.objects.count() == 2
    assert schedule_calls == []


@pytest.mark.django_db
def test_repeated_import_preserves_human_changes(tmp_path):
    """Повторный запуск пропускает mapped Album без перезаписи полей."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_profile_mapping(package, 0)
    CatalogReleaseImporter(package).run()
    album = Album.objects.get()
    album.name = 'Изменено человеком'
    album.description = 'Ручное описание'
    album.is_active = False
    album.save()

    result = CatalogReleaseImporter(package).run()

    album.refresh_from_db()
    assert result.created == 0
    assert result.already_mapped == 1
    assert Album.objects.count() == 1
    assert album.name == 'Изменено человеком'
    assert album.description == 'Ручное описание'
    assert album.is_active is False


@pytest.mark.django_db
def test_expanded_whitelist_keeps_registry_and_adds_related_release(tmp_path):
    """Расширение whitelist сохраняет старый mapping и добавляет новый."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_profile_mapping(package, 0)
    first = CatalogReleaseImporter(package).run()
    first_album = Album.objects.get()

    _set_whitelist(package, 0, 2)
    _create_profile_mapping(package, 2)

    result = CatalogReleaseImporter(package).run()

    assert result.selected == 2
    assert first.created == 1
    assert result.created == 1
    assert result.already_mapped == 1
    assert Album.objects.filter(pk=first_album.pk).exists()
    assert set(
        CatalogMigrationRegistry(package).get_mappings('release'),
    ) == {'release-00', 'release-02'}


@pytest.mark.django_db
def test_missing_profile_mapping_blocks_all_writes(tmp_path):
    """Отсутствующий mapping профиля обнаруживается до первой записи."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0, 1)
    _create_profile_mapping(package, 0)

    with pytest.raises(
        CatalogReleaseImportError,
        match='Mapping ArtistProfile отсутствует.*entity_id=release-01',
    ):
        CatalogReleaseImporter(package).run()

    assert Album.objects.count() == 0
    assert CatalogMigrationRegistry(package).get_mappings('release') == {}


@pytest.mark.django_db
def test_orphaned_profile_mapping_blocks_all_writes(tmp_path):
    """Осиротевший mapping профиля не приводит к скрытому профилю."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    CatalogMigrationRegistry(package).add_mapping(
        'profile',
        'profile-00',
        999999,
    )

    with pytest.raises(
        CatalogReleaseImportError,
        match='удалённый профиль.*entity_id=release-00',
    ):
        CatalogReleaseImporter(package).run()

    assert Album.objects.count() == 0


@pytest.mark.django_db
def test_conflicting_release_and_profile_mappings_are_rejected(tmp_path):
    """Mapped Album не может принадлежать другому mapped профилю."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_profile_mapping(package, 0)
    other_artist = ArtistProfile.objects.create(name='Other')
    album = Album.objects.bulk_create([
        Album(artist=other_artist, name='Existing draft'),
    ])[0]
    CatalogMigrationRegistry(package).add_mapping(
        'release',
        'release-00',
        album.pk,
    )

    with pytest.raises(
        CatalogReleaseImportError,
        match='конфликтует с mapping ArtistProfile.*entity_id=release-00',
    ):
        CatalogReleaseImporter(package).run()

    assert Album.objects.count() == 1


@pytest.mark.django_db
def test_orphaned_release_mapping_is_rejected(tmp_path):
    """RELEASE mapping с отсутствующим PK блокирует импорт."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_profile_mapping(package, 0)
    CatalogMigrationRegistry(package).add_mapping(
        'release',
        'release-00',
        999999,
    )

    with pytest.raises(
        CatalogReleaseImportError,
        match='удалённый релиз.*entity_id=release-00',
    ):
        CatalogReleaseImporter(package).run()

    assert Album.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_registry_failure_rolls_back_album(
    tmp_path,
    monkeypatch,
):
    """Сбой RELEASE mapping откатывает Album той же транзакцией."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_profile_mapping(package, 0)

    def fail_mapping(*args, **kwargs) -> Never:
        raise CatalogMigrationRegistryError('test registry failure')

    monkeypatch.setattr(
        CatalogMigrationRegistry,
        'add_mapping',
        fail_mapping,
    )

    with pytest.raises(
        CatalogReleaseImportError,
        match='Не удалось записать RELEASE mapping.*entity_id=release-00',
    ):
        CatalogReleaseImporter(package).run()

    assert Album.objects.count() == 0
    assert CatalogMigrationRegistry(package).get_mappings('release') == {}

    monkeypatch.undo()
    result = CatalogReleaseImporter(package).run()
    assert result.created == 1
    assert Album.objects.count() == 1


@pytest.mark.django_db
def test_disabled_releases_stage_creates_nothing(tmp_path):
    """Выключенный этап не требует mappings и не создаёт Album."""
    package = _make_package(tmp_path)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    config['enabled']['releases'] = False
    config['enabled']['tracks'] = False
    _write_json(config_path, config)

    result = CatalogReleaseImporter(package).run()

    assert result.selected == 0
    assert result.created == 0
    assert Album.objects.count() == 0
    assert CatalogMigrationMapping.objects.count() == 0


@pytest.mark.django_db
def test_exact_release_filter_creates_only_requested_entity(tmp_path):
    """Точечный trial-фильтр не импортирует другие релизы артиста."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0, 1)
    _create_profile_mapping(package, 0)
    _create_profile_mapping(package, 1)

    result = CatalogReleaseImporter(
        package,
        release_entity_id='release-00',
    ).run()

    assert result.selected == 1
    assert result.created == 1
    assert set(
        CatalogMigrationRegistry(package).get_mappings('release'),
    ) == {'release-00'}


@pytest.mark.django_db
def test_dry_run_validates_all_releases_without_writes(tmp_path):
    """Management dry-run проверяет выбранные строки и ничего не пишет."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0, 1)
    _create_profile_mapping(package, 0)
    _create_profile_mapping(package, 1)
    mappings_before = CatalogMigrationMapping.objects.count()
    output = StringIO()

    call_command(
        'import_catalog_releases',
        package,
        dry_run=True,
        stdout=output,
    )

    assert 'PREFLIGHT PASS' in output.getvalue()
    assert 'RELEASE IMPORT DRY-RUN' in output.getvalue()
    assert 'would_create=2' in output.getvalue()
    assert Album.objects.count() == 0
    assert CatalogMigrationRegistry(package).get_mappings('release') == {}
    assert CatalogMigrationMapping.objects.count() == mappings_before


@pytest.mark.django_db
def test_unknown_release_type_uses_visible_draft_default(tmp_path):
    """Неопределённый тип остаётся черновиком с видимым default-счётчиком."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_profile_mapping(package, 0)
    releases_path = package / BUNDLE_DIRECTORY / 'data' / 'releases.json'
    releases = _load(releases_path)
    releases[0]['is_single'] = None
    _write_json(releases_path, releases)

    result = CatalogReleaseImporter(package).run()

    album = Album.objects.get()
    assert album.is_single is False
    assert album.is_published is False
    assert result.defaulted_is_single == 1
    assert 'defaulted_is_single=1' in result.render()


@pytest.mark.django_db
@pytest.mark.parametrize('dry_run', [False, True])
def test_invalid_late_release_blocks_all_writes(tmp_path, dry_run):
    """Все выбранные Album валидируются до первой записи."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0, 1)
    _create_profile_mapping(package, 0)
    _create_profile_mapping(package, 1)
    releases_path = package / BUNDLE_DIRECTORY / 'data' / 'releases.json'
    releases = _load(releases_path)
    releases[1]['description'] = {'invalid': 'type'}
    _write_json(releases_path, releases)

    with pytest.raises(
        CatalogReleaseImportError,
        match='предварительную Django-валидацию.*entity_id=release-01',
    ):
        CatalogReleaseImporter(package, dry_run=dry_run).run()

    assert Album.objects.count() == 0


@pytest.mark.django_db
def test_duplicate_unmapped_release_titles_block_all_writes(tmp_path):
    """Два релиза одного артиста с одинаковым названием блокируют импорт."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_profile_mapping(package, 0)

    releases_path = package / BUNDLE_DIRECTORY / 'data' / 'releases.json'
    releases = _load(releases_path)
    releases[1]['profile_id'] = releases[0]['profile_id']
    releases[1]['title'] = releases[0]['title']
    _write_json(releases_path, releases)

    with pytest.raises(
        CatalogReleaseImportError,
        match='Два выбранных релиза без mapping',
    ):
        CatalogReleaseImporter(package).run()

    assert Album.objects.count() == 0
    assert CatalogMigrationRegistry(package).get_mappings('release') == {}
