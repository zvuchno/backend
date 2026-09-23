"""Тесты импорта дополнительных данных mapped-профилей."""

from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from catalog_migration.services.catalog_bundle import mapping_version
from catalog_migration.services.catalog_migration_preflight import (
    BUNDLE_VERSION,
)
from catalog_migration.services.catalog_profile_extras_import import (
    CatalogProfileExtrasImportError,
    CatalogProfileExtrasImporter,
)
from catalog_migration.services.catalog_profile_import import (
    CatalogProfileImporter,
)
from catalog_migration.tests.test_catalog_migration_preflight import (
    _code,
    _load,
    _make_package,
    _write_json,
)
from catalog_migration.tests.v2_package import v2_package

from store.models import CatalogMigrationMapping
from users.models import (
    ArtistContact,
    ArtistProfile,
    ArtistShippingPoint,
    ArtistSocial,
    ArtistStoreSettings,
)


def _prepare(tmp_path: Path) -> tuple[Path, ArtistProfile]:
    package = _make_package(tmp_path)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    config['artist_code_whitelist'] = [_code(0)]
    _write_json(config_path, config)
    profile = ArtistProfile.objects.create(
        name='Profile 0',
        slug=_code(0).lower(),
        user=None,
    )
    CatalogMigrationMapping.objects.create(
        bundle_version=BUNDLE_VERSION,
        entity_type=CatalogMigrationMapping.EntityType.PROFILE,
        source_entity_id='profile-00',
        django_pk=profile.pk,
    )
    return package, profile


@pytest.mark.django_db
def test_creates_contacts_telegram_and_pending_shipping_point(tmp_path):
    """Все четыре категории создаются без пользователя и доставки."""
    package, profile = _prepare(tmp_path)

    result = CatalogProfileExtrasImporter(package).run()

    profile.refresh_from_db()
    assert result.contacts.created == 1
    assert result.socials.created == 1
    assert result.telegram.created == 1
    assert result.cdek.created == 1
    assert profile.telegram_chat_id == 100
    assert ArtistContact.objects.filter(
        artist=profile,
        label='Email',
        value='public@example.com',
    ).exists()
    assert ArtistSocial.objects.filter(
        artist=profile,
        label='Website',
        value='https://example.com',
    ).exists()
    point = ArtistShippingPoint.objects.get(artist=profile)
    assert point.pvz_code == 'MSK1'
    assert point.city_code == '44'
    assert point.city == 'Москва'
    assert point.address == 'Москва'
    assert (
        ArtistStoreSettings.objects.get(
            artist=profile,
        ).shipping_enabled
        is False
    )
    assert profile.user_id is None
    assert get_user_model().objects.count() == 0


@pytest.mark.django_db
def test_repeated_import_creates_no_duplicates(tmp_path):
    """Повторный запуск распознаёт все существующие значения."""
    package, _ = _prepare(tmp_path)
    CatalogProfileExtrasImporter(package).run()

    result = CatalogProfileExtrasImporter(package).run()

    assert result.contacts.created == 0
    assert result.socials.created == 0
    assert result.telegram.created == 0
    assert result.cdek.created == 0
    assert result.contacts.existing == 1
    assert result.socials.existing == 1
    assert result.telegram.existing == 1
    assert result.cdek.existing == 1
    assert ArtistContact.objects.count() == 1
    assert ArtistSocial.objects.count() == 1
    assert ArtistShippingPoint.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize('occupied_by_other', [False, True])
def test_telegram_conflict_blocks_all_writes(tmp_path, occupied_by_other):
    """Другой chat профиля и chat другого профиля не перезаписываются."""
    package, profile = _prepare(tmp_path)
    if occupied_by_other:
        ArtistProfile.objects.create(
            name='Other profile',
            slug='other-profile',
            telegram_chat_id=100,
        )
    else:
        profile.telegram_chat_id = 200
        profile.save(update_fields=('telegram_chat_id',))

    with pytest.raises(CatalogProfileExtrasImportError, match='entity_id'):
        CatalogProfileExtrasImporter(package).run()

    profile.refresh_from_db()
    assert profile.telegram_chat_id == (None if occupied_by_other else 200)
    assert ArtistContact.objects.count() == 0
    assert ArtistSocial.objects.count() == 0
    assert ArtistShippingPoint.objects.count() == 0


@pytest.mark.django_db
def test_existing_contacts_are_preserved_without_update_or_delete(tmp_path):
    """Совпадающий и дополнительный ручной контакты сохраняются."""
    package, profile = _prepare(tmp_path)
    source = ArtistContact.objects.create(
        artist=profile,
        label='Email',
        value='public@example.com',
        is_active=False,
    )
    manual = ArtistContact.objects.create(
        artist=profile,
        label='Manager',
        value='manager@example.com',
    )

    result = CatalogProfileExtrasImporter(package).run()

    source.refresh_from_db()
    manual.refresh_from_db()
    assert result.contacts.created == 0
    assert result.contacts.existing == 1
    assert source.is_active is False
    assert manual.label == 'Manager'
    assert ArtistContact.objects.count() == 2


@pytest.mark.django_db
def test_manual_review_entry_is_skipped(tmp_path):
    """Общий контакт не разрешается автоматически."""
    package, _ = _prepare(tmp_path)
    path = package / 'public_contacts.json'
    document = _load(path)
    document['manual_review'][0]['value'] = 'public@example.com'
    _write_json(path, document)

    result = CatalogProfileExtrasImporter(package).run()

    assert result.contacts.selected == 0
    assert result.skipped_manual_review == 1
    assert result.skipped_entity_ids == ('profile-00',)
    assert ArtistContact.objects.count() == 0


@pytest.mark.django_db
def test_disabled_stages_create_nothing(tmp_path):
    """Выключенные extras не требуют записей и не включают доставку."""
    package, profile = _prepare(tmp_path)
    path = package / 'import_config.json'
    config = _load(path)
    for name in ('public_contacts', 'telegram', 'cdek'):
        config['enabled'][name] = False
    _write_json(path, config)

    result = CatalogProfileExtrasImporter(package).run()

    profile.refresh_from_db()
    assert result.contacts.selected == 0
    assert result.socials.selected == 0
    assert result.telegram.selected == 0
    assert result.cdek.selected == 0
    assert profile.telegram_chat_id is None
    assert not ArtistStoreSettings.objects.filter(artist=profile).exists()
    assert not ArtistShippingPoint.objects.filter(artist=profile).exists()


@pytest.mark.django_db
def test_dry_run_reports_plan_without_writes(tmp_path):
    """Dry-run выполняет все проверки, но не пишет extras."""
    package, profile = _prepare(tmp_path)

    result = CatalogProfileExtrasImporter(package, dry_run=True).run()

    assert result.contacts.would_create == 1
    assert result.socials.would_create == 1
    assert result.telegram.would_create == 1
    assert result.cdek.would_create == 1
    profile.refresh_from_db()
    assert profile.telegram_chat_id is None
    assert ArtistContact.objects.count() == 0
    assert ArtistSocial.objects.count() == 0
    assert ArtistShippingPoint.objects.count() == 0
    assert ArtistStoreSettings.objects.count() == 0


@pytest.mark.django_db
def test_management_command_dry_run(tmp_path):
    """Management-команда использует тот же read-only план."""
    package, _ = _prepare(tmp_path)
    output = StringIO()

    call_command(
        'import_catalog_profile_extras',
        package,
        dry_run=True,
        stdout=output,
    )

    assert 'PROFILE EXTRAS IMPORT DRY-RUN' in output.getvalue()
    assert 'contacts: selected=1' in output.getvalue()
    assert ArtistContact.objects.count() == 0
    assert ArtistShippingPoint.objects.count() == 0


@pytest.mark.django_db
def test_v2_public_contacts_only_dry_run_import_and_repeat(tmp_path):
    """v2 импортирует только публичные contacts/socials без дублей."""
    package = v2_package(tmp_path)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    config['artist_code_whitelist'] = [_code(0)]
    config['enabled']['public_contacts'] = True
    config['enabled']['telegram'] = False
    config['enabled']['cdek'] = False
    _write_json(config_path, config)
    contacts_path = package / 'public_contacts.json'
    contacts = _load(contacts_path)
    contacts['bundle_version'] = '2.0'
    _write_json(contacts_path, contacts)
    CatalogProfileImporter(package).run()
    profile = ArtistProfile.objects.get(
        pk=CatalogMigrationMapping.objects.get(
            bundle_version=mapping_version(package),
            entity_type=CatalogMigrationMapping.EntityType.PROFILE,
            source_entity_id='profile-00',
        ).django_pk,
    )
    manual = ArtistContact.objects.create(
        artist=profile,
        label='Manager',
        value='manual@example.com',
    )

    dry_run = CatalogProfileExtrasImporter(package, dry_run=True).run()

    assert dry_run.contacts.would_create == 1
    assert dry_run.socials.would_create == 1
    assert dry_run.telegram.selected == 0
    assert dry_run.cdek.selected == 0
    assert ArtistContact.objects.count() == 1
    assert ArtistSocial.objects.count() == 0

    created = CatalogProfileExtrasImporter(package).run()
    repeated = CatalogProfileExtrasImporter(package).run()

    assert created.contacts.created == 1
    assert created.socials.created == 1
    assert repeated.contacts.created == 0
    assert repeated.contacts.existing == 1
    assert repeated.socials.created == 0
    assert repeated.socials.existing == 1
    assert ArtistContact.objects.filter(pk=manual.pk).exists()
    assert ArtistContact.objects.count() == 2
    assert ArtistSocial.objects.count() == 1
    profile.refresh_from_db()
    assert profile.telegram_chat_id is None
    assert ArtistShippingPoint.objects.count() == 0
    assert ArtistStoreSettings.objects.count() == 0
