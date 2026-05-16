"""Тесты валидаторов файлов (размер, расширения)."""

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from store.constants import (
    ALLOWED_AUDIO_EXTENSIONS,
    MAX_AUDIOFILE_SIZE_MB,
    MAX_IMAGE_SIZE_MB,
)
from store.models import Album, Image, Merch, Track


class TestFileValidators:
    """Тесты валидации файлов."""

    @pytest.fixture(autouse=True)
    def _setup(self, user) -> None:
        self.album = Album.objects.create(
            name='Test_album',
            owner=user,
        )
        merch = Merch.objects.create(
            name='Test_merch',
            owner=user,
        )
        self.image_obj = Image.objects.create(
            merch=merch,
        )
        self.user = user

    # ========================== TESTS ==========================

    def test_validate_cover_image_size_success(self):
        """Допустимый размер обложки → проходит валидация."""
        file = SimpleUploadedFile(
            'cover.jpg',
            b'a',
            content_type='image/jpeg',
        )

        file.size = MAX_IMAGE_SIZE_MB * 1024 * 1024

        self.album.cover_image = file

        self.album.full_clean()

    def test_validate_cover_image_size_error(self):
        """Размер обложки больше допустимого → ошибка."""
        file = SimpleUploadedFile(
            'big_cover.jpg',
            b'a',
            content_type='image/jpeg',
        )

        file.size = (MAX_IMAGE_SIZE_MB + 1) * 1024 * 1024

        self.album.cover_image = file

        with pytest.raises(ValidationError) as exc:
            self.album.full_clean()

        assert 'cover_image' in exc.value.message_dict

    def test_merch_image_size_error(self):
        """Допустимый размер изображения → проходит валидация."""
        file = SimpleUploadedFile(
            'big_image.jpg',
            b'a',
            content_type='image/jpeg',
        )

        file.size = (MAX_IMAGE_SIZE_MB + 1) * 1024 * 1024

        self.image_obj.image = file

        with pytest.raises(ValidationError) as exc:
            self.image_obj.full_clean()
        assert 'image' in exc.value.message_dict

    def test_validate_audiofile_size_success(self):
        """Допустимый размер аудиофайла → проходит валидация."""
        file = SimpleUploadedFile(
            'track.mp3',
            b'a',
            content_type='audio/mpeg',
        )

        file.size = MAX_AUDIOFILE_SIZE_MB * 1024 * 1024

        track = Track(
            name='TestTrack',
            album=self.album,
            audio_file=file,
            owner=self.user,
        )

        track.full_clean()

    def test_validate_audiofile_size_error(self):
        """Размер аудиофайла превыжает допустимый → ошибка."""
        file = SimpleUploadedFile(
            'big_track.mp3',
            b'a',
            content_type='audio/mpeg',
        )

        file.size = (MAX_AUDIOFILE_SIZE_MB + 1) * 1024 * 1024

        track = Track(
            name='TestTrack',
            album=self.album,
            audio_file=file,
            owner=self.user,
        )

        with pytest.raises(ValidationError) as exc:
            track.full_clean()
        assert 'audio_file' in exc.value.message_dict

    @pytest.mark.parametrize('ext', ALLOWED_AUDIO_EXTENSIONS)
    def test_allowed_extensions_success(self, ext):
        """Разрешённые расширения → проходит валидация."""
        filename = f'track.{ext}'
        file = SimpleUploadedFile(
            filename,
            b'a',
            content_type='audio/mpeg',
        )

        track = Track(
            name='TestTrack',
            album=self.album,
            audio_file=file,
            owner=self.user,
        )

        track.full_clean()

    @pytest.mark.parametrize(
        'filename',
        [
            'track.jpg',
            'track.mp4',
        ],
    )
    def test_disallowed_extensions_error(self, filename):
        """Неразрешённые расширения → ошибка."""
        file = SimpleUploadedFile(
            filename,
            b'a',
            content_type='application/octet-stream',
        )

        track = Track(
            name='TestTrack',
            album=self.album,
            audio_file=file,
            owner=self.user,
        )

        with pytest.raises(ValidationError) as exc:
            track.full_clean()

        assert 'audio_file' in exc.value.message_dict
