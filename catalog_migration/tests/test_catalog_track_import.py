"""Тесты разового импорта метаданных Track из bundle v1.3."""

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
from catalog_migration.services.catalog_track_import import (
    CatalogTrackImportError,
    CatalogTrackImporter,
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
    Track,
    TrackGeneratedAudio,
    TrackUpload,
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


def _create_album_mapping(
    package,
    index: int,
    *,
    artist: ArtistProfile | None = None,
) -> Album:
    if artist is None:
        artist = _create_profile_mapping(package, index)
    album = Album.objects.bulk_create([
        Album(artist=artist, name=f'Release {index}'),
    ])[0]
    CatalogMigrationRegistry(package).add_mapping(
        'release',
        f'release-{index:02d}',
        album.pk,
    )
    return album


@pytest.mark.django_db
def test_first_import_creates_metadata_track_without_side_effects(
    tmp_path,
    monkeypatch,
):
    """Первый запуск создаёт только Track и mapping."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    album = _create_album_mapping(package, 0)
    audio_schedule_calls = []
    archive_schedule_calls = []
    monkeypatch.setattr(
        'store.services.audio.schedule.TrackGeneratedAudioScheduler.schedule',
        audio_schedule_calls.append,
    )
    monkeypatch.setattr(
        'store.services.album_archive.AlbumArchiveScheduler.schedule',
        archive_schedule_calls.append,
    )
    monkeypatch.setattr(
        'store.services.album_archive.AlbumArchiveScheduler.schedule_by_id',
        archive_schedule_calls.append,
    )

    result = CatalogTrackImporter(package).run()

    assert result.selected == 1
    assert result.created == 1
    assert result.already_mapped == 0
    track = Track.objects.get()
    assert track.album == album
    assert track.name == 'Track 0'
    assert track.position == 1
    assert track.description == ''
    assert track.duration is None
    assert track.created_by_id is None
    assert track.is_active is True
    assert not track.audio_file
    mapping = CatalogMigrationRegistry(package).get_mapping(
        'track',
        'track-00',
    )
    assert mapping == track.pk
    assert Product.objects.count() == 0
    assert TrackUpload.objects.count() == 0
    assert TrackGeneratedAudio.objects.count() == 0
    assert AlbumArchive.objects.count() == 0
    assert CatalogMigrationMapping.objects.count() == 3
    assert audio_schedule_calls == []
    assert archive_schedule_calls == []


@pytest.mark.django_db
def test_repeated_import_preserves_human_changes(tmp_path):
    """Повторный запуск не перезаписывает mapped Track."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_album_mapping(package, 0)
    CatalogTrackImporter(package).run()
    track = Track.objects.get()
    track.name = 'Изменено человеком'
    track.position = 42
    track.is_active = False
    track.save()

    result = CatalogTrackImporter(package).run()

    track.refresh_from_db()
    assert result.created == 0
    assert result.already_mapped == 1
    assert Track.objects.count() == 1
    assert track.name == 'Изменено человеком'
    assert track.position == 42
    assert track.is_active is False


@pytest.mark.django_db
def test_expanded_whitelist_keeps_registry_and_adds_related_track(tmp_path):
    """Расширение whitelist сохраняет старый mapping и добавляет новый."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_album_mapping(package, 0)
    first = CatalogTrackImporter(package).run()
    first_track = Track.objects.get()

    _set_whitelist(package, 0, 2)
    _create_album_mapping(package, 2)

    result = CatalogTrackImporter(package).run()

    assert result.selected == 2
    assert first.created == 1
    assert result.created == 1
    assert result.already_mapped == 1
    assert Track.objects.filter(pk=first_track.pk).exists()
    assert set(
        CatalogMigrationRegistry(package).get_mappings('track'),
    ) == {'track-00', 'track-02'}


@pytest.mark.django_db
def test_missing_album_mapping_blocks_all_writes(tmp_path):
    """Отсутствующий mapping Album обнаруживается до первой записи."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0, 1)
    _create_album_mapping(package, 0)
    _create_profile_mapping(package, 1)

    with pytest.raises(
        CatalogTrackImportError,
        match='Mapping Album отсутствует.*entity_id=track-01',
    ):
        CatalogTrackImporter(package).run()

    assert Track.objects.count() == 0
    assert CatalogMigrationRegistry(package).get_mappings('track') == {}


@pytest.mark.django_db
def test_orphaned_album_mapping_blocks_all_writes(tmp_path):
    """Осиротевший mapping Album не создаёт скрытый релиз."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_profile_mapping(package, 0)
    CatalogMigrationRegistry(package).add_mapping(
        'release',
        'release-00',
        999999,
    )

    with pytest.raises(
        CatalogTrackImportError,
        match='удалённый релиз.*entity_id=track-00',
    ):
        CatalogTrackImporter(package).run()

    assert Track.objects.count() == 0


@pytest.mark.django_db
def test_conflicting_album_mapping_blocks_all_writes(tmp_path):
    """Album mapping другого артиста считается конфликтом."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_profile_mapping(package, 0)
    other_artist = ArtistProfile.objects.create(name='Other')
    _create_album_mapping(package, 0, artist=other_artist)

    with pytest.raises(
        CatalogTrackImportError,
        match='конфликтует с mapping ArtistProfile.*entity_id=track-00',
    ):
        CatalogTrackImporter(package).run()

    assert Track.objects.count() == 0


@pytest.mark.django_db
def test_mapped_track_with_wrong_album_is_rejected(tmp_path):
    """TRACK mapping не может указывать в другой Album."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_album_mapping(package, 0)
    other_artist = ArtistProfile.objects.create(name='Other')
    other_album = Album.objects.bulk_create([
        Album(artist=other_artist, name='Other release'),
    ])[0]
    track = Track.objects.create(
        album=other_album,
        name='Existing track',
        position=1,
    )
    CatalogMigrationRegistry(package).add_mapping(
        'track',
        'track-00',
        track.pk,
    )

    with pytest.raises(
        CatalogTrackImportError,
        match='конфликтует с mapping Album.*entity_id=track-00',
    ):
        CatalogTrackImporter(package).run()

    assert Track.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_registry_failure_rolls_back_track_and_retry_succeeds(
    tmp_path,
    monkeypatch,
):
    """Сбой записи mapping откатывает Track вместе с транзакцией."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_album_mapping(package, 0)

    def fail_mapping(*args, **kwargs) -> Never:
        raise CatalogMigrationRegistryError('test registry failure')

    monkeypatch.setattr(
        CatalogMigrationRegistry,
        'add_mapping',
        fail_mapping,
    )

    with pytest.raises(
        CatalogTrackImportError,
        match='Не удалось записать TRACK mapping.*entity_id=track-00',
    ):
        CatalogTrackImporter(package).run()

    assert Track.objects.count() == 0
    assert CatalogMigrationRegistry(package).get_mappings('track') == {}

    monkeypatch.undo()
    result = CatalogTrackImporter(package).run()

    assert result.created == 1
    assert Track.objects.count() == 1


@pytest.mark.django_db
def test_disabled_tracks_stage_creates_nothing(tmp_path):
    """Выключенный этап не требует Album mappings."""
    package = _make_package(tmp_path)
    config_path = package / 'import_config.json'
    config = _load(config_path)
    config['enabled']['tracks'] = False
    _write_json(config_path, config)

    result = CatalogTrackImporter(package).run()

    assert result.selected == 0
    assert result.created == 0
    assert Track.objects.count() == 0
    assert CatalogMigrationMapping.objects.count() == 0


@pytest.mark.django_db
def test_exact_track_filter_creates_only_requested_entity(tmp_path):
    """Точечный trial-фильтр не импортирует другие треки артиста."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0, 1)
    _create_album_mapping(package, 0)
    _create_album_mapping(package, 1)

    result = CatalogTrackImporter(
        package,
        track_entity_id='track-00',
    ).run()

    assert result.selected == 1
    assert result.created == 1
    assert set(
        CatalogMigrationRegistry(package).get_mappings('track'),
    ) == {'track-00'}


@pytest.mark.django_db
def test_dry_run_management_command_does_not_write(tmp_path):
    """Management dry-run проверяет Track без записи."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0, 1)
    _create_album_mapping(package, 0)
    _create_album_mapping(package, 1)
    mappings_before = CatalogMigrationMapping.objects.count()
    output = StringIO()

    call_command(
        'import_catalog_tracks',
        package,
        dry_run=True,
        stdout=output,
    )

    assert 'PREFLIGHT PASS' in output.getvalue()
    assert 'TRACK IMPORT DRY-RUN' in output.getvalue()
    assert 'would_create=2' in output.getvalue()
    assert Track.objects.count() == 0
    assert CatalogMigrationRegistry(package).get_mappings('track') == {}
    assert CatalogMigrationMapping.objects.count() == mappings_before


@pytest.mark.django_db
def test_import_preserves_exact_bundle_position(tmp_path):
    """Position берётся из tracks.json без вычислений и догадок."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0)
    _create_album_mapping(package, 0)
    tracks_path = package / BUNDLE_DIRECTORY / 'data' / 'tracks.json'
    tracks = _load(tracks_path)
    tracks[0]['position'] = 37
    _write_json(tracks_path, tracks)

    CatalogTrackImporter(package).run()

    assert Track.objects.get().position == 37


@pytest.mark.django_db
@pytest.mark.parametrize('dry_run', [False, True])
def test_invalid_late_track_blocks_all_writes(tmp_path, dry_run):
    """Все выбранные Track валидируются до первой записи."""
    package = _make_package(tmp_path)
    _set_whitelist(package, 0, 1)
    _create_album_mapping(package, 0)
    _create_album_mapping(package, 1)
    tracks_path = package / BUNDLE_DIRECTORY / 'data' / 'tracks.json'
    tracks = _load(tracks_path)
    tracks[1]['title'] = 'X' * 300
    _write_json(tracks_path, tracks)

    with pytest.raises(
        CatalogTrackImportError,
        match='предварительную Django-валидацию.*entity_id=track-01',
    ):
        CatalogTrackImporter(package, dry_run=dry_run).run()

    assert Track.objects.count() == 0
