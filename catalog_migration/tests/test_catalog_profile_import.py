"""Тесты разового импорта ArtistProfile из bundle v1.3."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework import status

from catalog_migration.services.catalog_migration_preflight import (
    BUNDLE_DIRECTORY,
)
from catalog_migration.services.catalog_migration_registry import (
    CatalogMigrationRegistry,
    CatalogMigrationRegistryError,
)
from catalog_migration.services.catalog_profile_import import (
    CatalogProfileImportError,
    CatalogProfileImporter,
)
from catalog_migration.tests.test_catalog_migration_preflight import (
    _code,
    _load,
    _make_package,
    _write_json,
)

from store.models import CatalogMigrationMapping
from users.models import ArtistProfile, ArtistProfileType


def _set_whitelist(package, *profile_indexes: int) -> None:
    """Оставляет в тестовом whitelist выбранные профили."""
    path = package / 'import_config.json'
    config = _load(path)
    config['artist_code_whitelist'] = [
        _code(index) for index in profile_indexes
    ]
    _write_json(path, config)


def _set_label_relation(package) -> None:
    """Делает первый профиль лейблом второго профиля."""
    path = package / BUNDLE_DIRECTORY / 'data' / 'profiles.json'
    profiles = _load(path)
    profiles[0]['profile_type'] = 'LABEL'
    profiles[1]['parent_label_id'] = profiles[0]['entity_id']
    _write_json(path, profiles)


@pytest.mark.django_db
def test_first_import_creates_active_unclaimed_profile_and_registry_entry(
    tmp_path,
):
    """Первый запуск создаёт активный профиль и DB mapping."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)

    result = CatalogProfileImporter(package).run()

    assert result.selected == 1
    assert result.created == 1
    assert result.already_mapped == 0
    profile = ArtistProfile.objects.get()
    assert profile.slug == _code(0).lower()
    assert profile.is_active is True
    assert profile.user_id is None
    assert profile.telegram_chat_id is None
    assert not profile.cover
    registry = CatalogMigrationRegistry(package)
    assert registry.get_mapping('profile', 'profile-00') == profile.pk
    assert CatalogMigrationMapping.objects.count() == 1


@pytest.mark.django_db
def test_repeated_import_skips_registry_entry_and_preserves_human_changes(
    tmp_path,
):
    """Повторный запуск не создаёт дубль и не откатывает правки."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    CatalogProfileImporter(package).run()
    profile = ArtistProfile.objects.get()
    profile.name = 'Изменено человеком'
    profile.is_active = False
    profile.save()

    result = CatalogProfileImporter(package).run()

    profile.refresh_from_db()
    assert result.created == 0
    assert result.already_mapped == 1
    assert ArtistProfile.objects.count() == 1
    assert profile.name == 'Изменено человеком'
    assert profile.is_active is False


@pytest.mark.django_db
def test_extending_whitelist_preserves_registry_and_adds_profile(tmp_path):
    """Расширение whitelist дополняет, но не инвалидирует реестр."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    CatalogProfileImporter(package).run()
    first = ArtistProfile.objects.get()
    _set_whitelist(package, 0, 2)

    result = CatalogProfileImporter(package).run()

    registry = CatalogMigrationRegistry(package)
    assert result.created == 1
    assert result.already_mapped == 1
    assert registry.get_mapping('profile', 'profile-00') == first.pk
    assert set(registry.get_mappings('profile')) == {
        'profile-00',
        'profile-02',
    }


@pytest.mark.django_db
def test_disabled_profiles_stage_creates_nothing(tmp_path):
    """Полностью отключённая зависимая цепочка не пишет профили."""
    package = _make_package(tmp_path)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    config['enabled'] = {stage: False for stage in config['enabled']}
    _write_json(config_path, config)

    result = CatalogProfileImporter(package).run()

    assert result.selected == 0
    assert result.created == 0
    assert ArtistProfile.objects.count() == 0
    assert CatalogMigrationMapping.objects.count() == 0


@pytest.mark.django_db
def test_failed_preflight_blocks_database_writes(tmp_path):
    """Импорт не обращается к записи до успешного preflight."""
    package = _make_package(tmp_path)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    config['artist_code_whitelist'].append('ZZZZ')
    _write_json(config_path, config)

    with pytest.raises(CatalogProfileImportError, match='PREFLIGHT FAIL'):
        CatalogProfileImporter(package).run()

    assert ArtistProfile.objects.count() == 0
    assert CatalogMigrationMapping.objects.count() == 0


@pytest.mark.django_db
def test_existing_slug_without_registry_is_conflict_case_insensitively(
    tmp_path,
):
    """Похожий slug не используется как неявное соответствие."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    ArtistProfile.objects.create(
        name='Existing',
        slug=_code(0).upper(),
    )

    with pytest.raises(
        CatalogProfileImportError,
        match='Slug уже занят.*entity_id=profile-00',
    ):
        CatalogProfileImporter(package).run()

    assert CatalogMigrationMapping.objects.count() == 0
    assert ArtistProfile.objects.count() == 1


@pytest.mark.django_db
def test_registry_to_deleted_profile_blocks_replacement(tmp_path):
    """Осиротевший реестр не позволяет автоматически создать замену."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    CatalogProfileImporter(package).run()
    ArtistProfile.objects.get().delete()

    with pytest.raises(
        CatalogProfileImportError,
        match='Реестр указывает на удалённый ArtistProfile.*profile-00',
    ):
        CatalogProfileImporter(package).run()

    assert ArtistProfile.objects.count() == 0
    assert (
        CatalogMigrationRegistry(package).get_mapping(
            'profile',
            'profile-00',
        )
        is not None
    )


@pytest.mark.django_db
def test_registry_write_failure_rolls_back_profile(tmp_path, monkeypatch):
    """Сбой DB mapping откатывает профиль вместе с транзакцией."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)

    with monkeypatch.context() as context:
        context.setattr(
            CatalogMigrationRegistry,
            'add_mapping',
            lambda *args, **kwargs: (_ for _ in ()).throw(
                CatalogMigrationRegistryError('write failed'),
            ),
        )
        with pytest.raises(
            CatalogProfileImportError,
            match='Не удалось записать mapping.*profile-00',
        ):
            CatalogProfileImporter(package).run()

    assert ArtistProfile.objects.count() == 0
    assert CatalogMigrationMapping.objects.count() == 0
    result = CatalogProfileImporter(package).run()
    assert result.created == 1


@pytest.mark.django_db
def test_selected_artist_is_linked_to_selected_label(tmp_path):
    """Выбранный артист связывается только с выбранным лейблом."""
    package = _make_package(tmp_path)
    _set_label_relation(package)
    _set_whitelist(package, 0, 1)

    result = CatalogProfileImporter(package).run()

    assert result.created == 2
    label = ArtistProfile.objects.get(slug=_code(0).lower())
    artist = ArtistProfile.objects.get(slug=_code(1).lower())
    assert label.profile_type == ArtistProfileType.LABEL
    assert artist.profile_type == ArtistProfileType.ARTIST
    assert artist.label == label
    assert CatalogMigrationMapping.objects.count() == 2


@pytest.mark.django_db
def test_parent_label_outside_whitelist_blocks_all_writes(tmp_path):
    """Обязательный внешний лейбл не включается в импорт неявно."""
    package = _make_package(tmp_path)
    _set_label_relation(package)
    _set_whitelist(package, 1)

    with pytest.raises(
        CatalogProfileImportError,
        match='parent_label_id находится вне whitelist.*entity_id=profile-01',
    ):
        CatalogProfileImporter(package).run()

    assert ArtistProfile.objects.count() == 0
    assert CatalogMigrationMapping.objects.count() == 0


@pytest.mark.django_db
def test_dry_run_management_command_does_not_write(tmp_path):
    """Пробный запуск команды выполняет проверки без записи."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    output = StringIO()

    call_command(
        'import_catalog_profiles',
        package,
        dry_run=True,
        stdout=output,
    )

    assert 'PREFLIGHT PASS' in output.getvalue()
    assert 'PROFILE IMPORT DRY-RUN' in output.getvalue()
    assert ArtistProfile.objects.count() == 0
    assert CatalogMigrationMapping.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize('dry_run', [False, True])
def test_all_selected_profiles_are_validated_before_first_write(
    tmp_path,
    dry_run,
):
    """Поздняя невалидная строка блокирует весь запуск до записи."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0, 1)
    profiles_path = package / BUNDLE_DIRECTORY / 'data' / 'profiles.json'
    profiles = _load(profiles_path)
    profiles[1]['display_name'] = 'X'
    _write_json(profiles_path, profiles)

    with pytest.raises(
        CatalogProfileImportError,
        match='предварительную Django-валидацию.*entity_id=profile-01',
    ):
        CatalogProfileImporter(package, dry_run=dry_run).run()

    assert ArtistProfile.objects.count() == 0
    assert CatalogMigrationMapping.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.usefixtures('publication_readiness_enabled')
def test_imported_ownerless_profile_is_not_public(
    tmp_path,
    api_client,
):
    """Профиль без владельца не обходит правила публичной готовности."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    CatalogProfileImporter(package).run()
    profile = ArtistProfile.objects.get()

    detail_response = api_client.get(
        reverse(
            'api:users:artist_public',
            kwargs={'slug': profile.slug},
        ),
    )
    list_response = api_client.get(reverse('api:users:artist_list'))

    assert detail_response.status_code == status.HTTP_404_NOT_FOUND
    assert list_response.status_code == status.HTTP_200_OK
    profile_ids = {item['id'] for item in list_response.data['results']}
    assert profile.id not in profile_ids


@pytest.mark.django_db
def test_swapped_registry_pk_is_rejected(tmp_path):
    """Не принимает PK другого импортированного профиля."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0, 1)
    CatalogProfileImporter(package).run()

    first = CatalogMigrationMapping.objects.get(
        source_entity_id='profile-00',
    )
    CatalogMigrationMapping.objects.filter(pk=first.pk).update(
        source_entity_id='temporary-source-id',
    )
    CatalogMigrationMapping.objects.filter(
        source_entity_id='profile-01',
    ).update(source_entity_id='profile-00')
    CatalogMigrationMapping.objects.filter(pk=first.pk).update(
        source_entity_id='profile-01',
    )

    with pytest.raises(
        CatalogProfileImportError,
        match='Реестр указывает на другой ArtistProfile',
    ):
        CatalogProfileImporter(package).run()

    assert ArtistProfile.objects.count() == 2
