"""Тесты бонусов релиза."""

from io import BytesIO
from zipfile import ZipFile

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from store.models import AlbumArchive, Bonus
from store.services.album_archive import (
    AlbumArchiveScheduler,
    AlbumArchiveService,
)
from store.tests.factories import AlbumFactory, BonusFactory, TrackFactory
from store.validators import FileSizeValidator


@pytest.fixture
def album(artist_user):
    """Создаёт опубликованный альбом артиста."""
    return AlbumFactory(
        artist=artist_user.artist_profile,
        is_published=True,
    )


@pytest.fixture
def bonus(album):
    """Создаёт бонус альбома."""
    return BonusFactory(album=album)


class TestBonusAPI:
    """Проверяет API бонусов."""

    def test_create_bonus(
        self,
        artist_client,
        bonus_list_url,
        album,
    ):
        """Артист может создать бонус в своём альбоме."""
        response = artist_client.post(
            bonus_list_url,
            {
                'name': 'Booklet',
                'bonus_file': SimpleUploadedFile(
                    'booklet.pdf',
                    b'pdf-content',
                    content_type='application/pdf',
                ),
                'description': 'Цифровой буклет.',
                'album': album.id,
            },
            format='multipart',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Booklet'

        bonus = Bonus.objects.get(name='Booklet')
        assert bonus.album_id == album.id
        assert bonus.description == 'Цифровой буклет.'

    def test_list_bonuses(
        self,
        artist_client,
        bonus_list_url,
        bonus,
    ):
        """Артист видит бонусы своих альбомов."""
        response = artist_client.get(bonus_list_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
        assert response.data['results'][0]['name'] == bonus.name

    def test_retrieve_bonus(
        self,
        artist_client,
        bonus_detail_url,
        bonus,
    ):
        """Артист получает подробную информацию о бонусе."""
        response = artist_client.get(bonus_detail_url(bonus))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == bonus.name
        assert response.data['description'] == bonus.description
        assert 'bonus_file' in response.data

    def test_update_bonus(
        self,
        artist_client,
        bonus_detail_url,
        bonus,
    ):
        """Артист может изменить бонус."""
        response = artist_client.patch(
            bonus_detail_url(bonus),
            {
                'name': 'Новый буклет',
                'description': 'Новое описание.',
            },
            format='multipart',
        )

        assert response.status_code == status.HTTP_200_OK
        bonus.refresh_from_db()

        assert bonus.name == 'Новый буклет'
        assert bonus.description == 'Новое описание.'

    def test_delete_bonus(
        self,
        artist_client,
        bonus_detail_url,
        bonus,
    ):
        """Удаление бонуса выполняется мягко."""
        response = artist_client.delete(bonus_detail_url(bonus))

        assert response.status_code == status.HTTP_204_NO_CONTENT

        bonus.refresh_from_db()
        assert bonus.is_active is False

    def test_cannot_create_bonus_in_foreign_album(
        self,
        artist_client,
        bonus_list_url,
    ):
        """Артист не может добавить бонус в чужой альбом."""
        foreign_album = AlbumFactory(is_published=True)

        response = artist_client.post(
            bonus_list_url,
            {
                'name': 'Booklet',
                'bonus_file': (
                    'booklet.pdf',
                    b'pdf-content',
                    'application/pdf',
                ),
                'album': foreign_album.id,
            },
            format='multipart',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_foreign_bonus_is_not_available(
        self,
        artist_client,
        bonus_detail_url,
    ):
        """Артист не может получить чужой бонус."""
        foreign_bonus = BonusFactory()

        response = artist_client.get(
            bonus_detail_url(foreign_bonus),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize(
        'filename',
        [
            'bonus.pdf',
            'bonus.jpg',
            'bonus.png',
            'bonus.mp4',
            'bonus.txt',
            'bonus.zip',
        ],
    )
    def test_create_bonus_with_allowed_extensions(
        self,
        artist_client,
        bonus_list_url,
        album,
        filename,
    ):
        """Бонусы с разрешёнными расширениями принимаются."""
        response = artist_client.post(
            bonus_list_url,
            {
                'name': 'Bonus',
                'bonus_file': SimpleUploadedFile(
                    filename,
                    b'test-content',
                ),
                'album': album.id,
            },
            format='multipart',
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_bonus_with_forbidden_extension(
        self,
        artist_client,
        bonus_list_url,
        album,
    ):
        """Бонус с запрещённым расширением отклоняется."""
        response = artist_client.post(
            bonus_list_url,
            {
                'name': 'Bonus',
                'bonus_file': SimpleUploadedFile(
                    'bonus.mp3',
                    b'test-content',
                ),
                'album': album.id,
            },
            format='multipart',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'bonus_file' in response.data


class TestBonusFileValidation:
    """Проверяет валидацию файлов бонусов."""

    def test_file_size_limit(self):
        """Файл больше допустимого размера отклоняется."""
        validator = FileSizeValidator(500)
        bonus_file = SimpleUploadedFile(
            'bonus.pdf',
            b'test-content',
        )
        bonus_file.size = 501 * 1024 * 1024

        with pytest.raises(
            DjangoValidationError,
            match=r'превышает лимит 500 MB',
        ):
            validator(bonus_file)


class TestBonusArchive:
    """Проверяет включение бонусов в архив альбома."""

    def test_bonus_is_included_in_album_archive(self, album):
        """Активный бонус попадает в архив альбома."""
        track = TrackFactory(
            album=album,
            is_active=True,
            position=1,
        )
        bonus = BonusFactory(
            album=album,
            is_active=True,
        )

        content_hash = AlbumArchiveService.calculate_content_hash(
            album=album,
            tracks=[track],
            bonuses=[bonus],
        )

        AlbumArchive.objects.create(
            album=album,
            pending_hash=content_hash,
        )

        archive = AlbumArchiveService.build(
            album_id=album.id,
            expected_hash=content_hash,
        )

        with ZipFile(BytesIO(archive.file.read())) as zip_file:
            names = zip_file.namelist()

        assert f'01 - {track.name}.mp3' in names
        assert f'bonuses/{bonus.name}.pdf' in names

    def test_inactive_bonus_is_not_included_in_album_archive(self, album):
        """Неактивный бонус не попадает в архив альбома."""
        track = TrackFactory(
            album=album,
            is_active=True,
            position=1,
        )
        bonus = BonusFactory(
            album=album,
            is_active=False,
        )

        content_hash = AlbumArchiveService.calculate_content_hash(
            album=album,
            tracks=[track],
            bonuses=[],
        )

        AlbumArchive.objects.create(
            album=album,
            pending_hash=content_hash,
        )

        archive = AlbumArchiveService.build(
            album_id=album.id,
            expected_hash=content_hash,
        )

        with ZipFile(BytesIO(archive.file.read())) as zip_file:
            names = zip_file.namelist()

        assert f'01 - {track.name}.mp3' in names
        assert f'bonuses/{bonus.name}.pdf' not in names

    def test_adding_bonus_changes_archive_hash(
        self,
        album,
    ):
        """Добавление бонуса меняет hash содержимого архива."""
        TrackFactory(
            album=album,
            position=1,
        )
        assert AlbumArchiveScheduler.schedule(album) is True

        archive = AlbumArchive.objects.get(album=album)
        initial_hash = archive.pending_hash

        BonusFactory(
            album=album,
            is_active=True,
        )

        assert AlbumArchiveScheduler.schedule(album) is True

        archive.refresh_from_db()

        assert archive.pending_hash != initial_hash

    def test_creating_bonus_schedules_archive_rebuild(
        self,
        album,
        monkeypatch,
        django_capture_on_commit_callbacks,
    ):
        """Создание бонуса планирует пересборку архива."""
        scheduled_album_ids = []

        def schedule_by_id(album_id) -> None:
            scheduled_album_ids.append(album_id)

        monkeypatch.setattr(
            AlbumArchiveScheduler,
            'schedule_by_id',
            schedule_by_id,
        )

        with django_capture_on_commit_callbacks(execute=True):
            BonusFactory(album=album)

        assert scheduled_album_ids == [album.id]
