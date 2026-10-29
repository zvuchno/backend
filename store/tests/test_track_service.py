from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from store.constants import CHAR_PRESET_DIGITAL, ZERO_MONEY
from store.models import Album, Product, Recording, ReleaseTrack
from store.services.album_archive import AlbumArchiveScheduler
from store.services.track import TrackService
from store.tests.factories import (
    AlbumFactory,
    RecordingFactory,
    ReleaseTrackFactory,
)


@pytest.mark.django_db
class TestAddRecording:
    """Добавление существующей мастер-записи в релиз."""

    def test_creates_placement_and_commerce(
        self,
        artist_user,
    ):
        """Создаёт размещение, товар и цифровой вариант."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
        )
        recording_count = Recording.objects.count()

        track = TrackService.add_recording(
            release=album,
            recording=recording,
            user=artist_user,
            price=Decimal('150.00'),
            allow_overpay=True,
        )

        assert track.release_id == album.pk
        assert track.recording_id == recording.pk
        assert track.position == 1
        assert track.is_active is True

        assert Recording.objects.count() == recording_count

        product = track.product
        assert product.product_type == Product.ProductType.TRACK
        assert product.price == Decimal('150.00')
        assert product.allow_overpay is True

        assert (
            product.variants.filter(
                property_value=CHAR_PRESET_DIGITAL,
                is_active=True,
                stock__isnull=True,
            ).count()
            == 1
        )

    def test_superuser_places_recording_in_owners_release(
        self,
        artist_user,
        staff_user,
    ):
        """Суперпользователь размещает запись в релизе её владельца."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
        )

        track = TrackService.add_recording(
            release=album,
            recording=recording,
            user=staff_user,
        )

        assert track.release_id == album.pk
        assert track.recording_id == recording.pk
        assert track.product.product_type == Product.ProductType.TRACK

    def test_superuser_cannot_mix_independent_artists(
        self,
        artist_user,
        other_artist_user,
        staff_user,
    ):
        """Полномочия суперпользователя не обходят совместимость профилей."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=other_artist_user.artist_profile,
            created_by=other_artist_user,
        )
        product_count = Product.objects.count()

        with pytest.raises(ValidationError) as exc_info:
            TrackService.add_recording(
                release=album,
                recording=recording,
                user=staff_user,
            )

        assert 'recording_id' in exc_info.value.detail
        assert not ReleaseTrack.objects.filter(
            release=album,
            recording=recording,
        ).exists()
        assert Product.objects.count() == product_count

    def test_superuser_cannot_mix_different_labels(
        self,
        artist_profile_factory,
        label_user_factory,
        signed_artist_user,
        staff_user,
    ):
        """Записи артистов разных лейблов несовместимы."""
        other_label_user = label_user_factory(
            email='other-label@test.com',
            username='other_label',
        )
        other_label_artist = artist_profile_factory(
            user=None,
            label=other_label_user.artist_profile,
            name='Other Label Artist',
        )
        album = AlbumFactory(
            artist=signed_artist_user.artist_profile,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=other_label_artist,
            created_by=other_label_user,
        )

        with pytest.raises(ValidationError) as exc_info:
            TrackService.add_recording(
                release=album,
                recording=recording,
                user=staff_user,
            )

        assert 'recording_id' in exc_info.value.detail
        assert not album.tracks.filter(recording=recording).exists()

    def test_assigns_next_position(
        self,
        artist_user,
    ):
        """Новое размещение получает следующую позицию."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            is_published=False,
        )
        ReleaseTrackFactory(
            release=album,
            position=3,
        )
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
        )

        track = TrackService.add_recording(
            release=album,
            recording=recording,
            user=artist_user,
        )

        assert track.position == 4

    def test_same_recording_in_different_releases(
        self,
        artist_user,
    ):
        """Одна запись используется в разных релизах с разными ценами."""
        first_album = AlbumFactory(
            artist=artist_user.artist_profile,
            is_published=False,
        )
        second_album = AlbumFactory(
            artist=artist_user.artist_profile,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
        )

        recording_count = Recording.objects.count()
        original_name = recording.audio_file.name

        first_track = TrackService.add_recording(
            release=first_album,
            recording=recording,
            user=artist_user,
            price=Decimal('100.00'),
            allow_overpay=False,
        )
        second_track = TrackService.add_recording(
            release=second_album,
            recording=recording,
            user=artist_user,
            price=Decimal('250.00'),
            allow_overpay=True,
        )

        recording.refresh_from_db()

        assert first_track.pk != second_track.pk
        assert first_track.recording_id == recording.pk
        assert second_track.recording_id == recording.pk

        assert first_track.product.price == Decimal('100.00')
        assert first_track.product.allow_overpay is False

        assert second_track.product.price == Decimal('250.00')
        assert second_track.product.allow_overpay is True

        assert Recording.objects.count() == recording_count
        assert recording.audio_file.name == original_name
        assert recording.release_tracks.count() == 2

    def test_label_can_place_managed_artist_recording(
        self,
        label_user,
        label_created_artist,
        signed_artist_user,
    ):
        """Лейбл размещает запись одного артиста в релизе другого."""
        album = AlbumFactory(
            artist=signed_artist_user.artist_profile,
            created_by=signed_artist_user,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=label_created_artist,
            created_by=label_user,
        )

        track = TrackService.add_recording(
            release=album,
            recording=recording,
            user=label_user,
            price=Decimal('200.00'),
        )

        assert track.recording.owner_id == label_created_artist.pk
        assert track.release.artist_id == signed_artist_user.artist_profile.pk
        assert track.product.price == Decimal('200.00')

        recording.refresh_from_db()
        assert recording.owner_id == label_created_artist.pk

    @pytest.mark.parametrize(
        'release_owner',
        ('label', 'artist'),
    )
    def test_label_and_managed_artist_recordings_are_compatible(
        self,
        label_user,
        signed_artist_user,
        release_owner,
    ):
        """Профиль лейбла и его артист совместимы в обоих направлениях."""
        label = label_user.artist_profile
        artist = signed_artist_user.artist_profile
        album_artist = label if release_owner == 'label' else artist
        recording_owner = artist if release_owner == 'label' else label
        album = AlbumFactory(
            artist=album_artist,
            created_by=label_user,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=recording_owner,
            created_by=label_user,
        )

        track = TrackService.add_recording(
            release=album,
            recording=recording,
            user=label_user,
        )

        assert track.release_id == album.pk
        assert track.recording_id == recording.pk

    def test_artist_cannot_use_other_artist_recording_from_same_label(
        self,
        label_created_artist,
        signed_artist_user,
    ):
        """Общий лейбл не даёт артисту права на чужую запись."""
        album = AlbumFactory(
            artist=signed_artist_user.artist_profile,
            created_by=signed_artist_user,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=label_created_artist,
        )
        product_count = Product.objects.count()

        with pytest.raises(PermissionDenied):
            TrackService.add_recording(
                release=album,
                recording=recording,
                user=signed_artist_user,
            )

        assert not album.tracks.filter(recording=recording).exists()
        assert Product.objects.count() == product_count

    def test_staff_has_no_superuser_access(
        self,
        artist_user,
        user_factory,
    ):
        """Обычный staff не управляет чужим релизом и записью."""
        staff = user_factory(
            email='track-staff@test.com',
            username='track_staff',
            is_staff=True,
            is_superuser=False,
        )
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
        )

        with pytest.raises(PermissionDenied):
            TrackService.add_recording(
                release=album,
                recording=recording,
                user=staff,
            )

        assert not album.tracks.filter(recording=recording).exists()

    @pytest.mark.parametrize(
        'forbidden_object',
        ('release', 'recording'),
    )
    def test_requires_access_to_both_objects(
        self,
        artist_user,
        other_artist_user,
        forbidden_object,
    ):
        """Нужны независимые права на релиз и мастер-запись."""
        own_artist = artist_user.artist_profile
        foreign_artist = other_artist_user.artist_profile

        if forbidden_object == 'release':
            album = AlbumFactory(
                artist=foreign_artist,
                created_by=other_artist_user,
                is_published=False,
            )
            recording = RecordingFactory(
                owner=own_artist,
                created_by=artist_user,
            )
        else:
            album = AlbumFactory(
                artist=own_artist,
                created_by=artist_user,
                is_published=False,
            )
            recording = RecordingFactory(
                owner=foreign_artist,
                created_by=other_artist_user,
            )

        with pytest.raises(PermissionDenied):
            TrackService.add_recording(
                release=album,
                recording=recording,
                user=artist_user,
                price=Decimal('100.00'),
            )

        assert not ReleaseTrack.objects.filter(
            release=album,
            recording=recording,
        ).exists()

    def test_label_cannot_use_unmanaged_recording(
        self,
        label_user,
        signed_artist_user,
        other_artist_user,
    ):
        """Лейбл не может использовать запись стороннего артиста."""
        album = AlbumFactory(
            artist=signed_artist_user.artist_profile,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=other_artist_user.artist_profile,
            created_by=other_artist_user,
        )

        with pytest.raises(PermissionDenied):
            TrackService.add_recording(
                release=album,
                recording=recording,
                user=label_user,
            )

        assert not album.tracks.exists()

    @pytest.mark.parametrize(
        'deactivated',
        (False, True),
    )
    def test_rejects_duplicate_placement(
        self,
        artist_user,
        deactivated,
    ):
        """Повторное добавление не меняет существующий товар."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
        )

        first_track = TrackService.add_recording(
            release=album,
            recording=recording,
            user=artist_user,
            price=Decimal('100.00'),
        )

        if deactivated:
            first_track.is_active = False
            first_track.save(update_fields=('is_active',))

        with pytest.raises(ValidationError):
            TrackService.add_recording(
                release=album,
                recording=recording,
                user=artist_user,
                price=Decimal('500.00'),
            )

        first_track.product.refresh_from_db()

        assert (
            ReleaseTrack.objects.filter(
                release=album,
                recording=recording,
            ).count()
            == 1
        )
        assert first_track.product.price == Decimal('100.00')

    @pytest.mark.parametrize(
        'recording_kwargs',
        (
            pytest.param(
                {'audio_file': ''},
                id='missing-original',
            ),
            pytest.param(
                {'is_active': False},
                id='inactive-recording',
            ),
        ),
    )
    def test_rejects_unavailable_recording(
        self,
        artist_user,
        recording_kwargs,
    ):
        """Не размещает запись без оригинала или неактивную запись."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
            **recording_kwargs,
        )

        with pytest.raises(ValidationError):
            TrackService.add_recording(
                release=album,
                recording=recording,
                user=artist_user,
            )

        assert not album.tracks.exists()

    def test_single_uses_release_commerce(
        self,
        artist_user,
    ):
        """Сингл не требует индивидуальной цены трека."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            release_type=Album.ReleaseType.SINGLE,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
        )

        track = TrackService.add_recording(
            release=album,
            recording=recording,
            user=artist_user,
        )

        assert track.is_active is True
        assert track.product.price == ZERO_MONEY
        assert track.product.allow_overpay is False

    @pytest.mark.parametrize(
        ('price', 'allow_overpay'),
        (
            pytest.param(
                Decimal('100.00'),
                False,
                id='individual-price',
            ),
            pytest.param(
                None,
                True,
                id='individual-overpay',
            ),
        ),
    )
    def test_single_rejects_individual_commerce(
        self,
        artist_user,
        price,
        allow_overpay,
    ):
        """Сингл не разрешает цену или переплату отдельного трека."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            release_type=Album.ReleaseType.SINGLE,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
        )

        with pytest.raises(ValidationError):
            TrackService.add_recording(
                release=album,
                recording=recording,
                user=artist_user,
                price=price,
                allow_overpay=allow_overpay,
            )

        assert not album.tracks.exists()

    def test_published_single_rejects_second_track(
        self,
        artist_user,
    ):
        """В опубликованный сингл нельзя добавить второй активный трек."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            release_type=Album.ReleaseType.SINGLE,
            is_published=True,
        )
        ReleaseTrackFactory(
            release=album,
            position=1,
            is_active=True,
        )
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
        )

        with pytest.raises(ValidationError):
            TrackService.add_recording(
                release=album,
                recording=recording,
                user=artist_user,
            )

        assert album.tracks.count() == 1
        assert not album.tracks.filter(recording=recording).exists()

    def test_invalid_price_rolls_back_placement(
        self,
        artist_user,
    ):
        """Ошибка коммерческой валидации откатывает создание размещения."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
        )

        with pytest.raises(ValidationError):
            TrackService.add_recording(
                release=album,
                recording=recording,
                user=artist_user,
                price=Decimal('1.12345'),
            )

        assert not ReleaseTrack.objects.filter(
            release=album,
            recording=recording,
        ).exists()

        assert Recording.objects.filter(pk=recording.pk).exists()

    def test_rejects_negative_price(
        self,
        artist_user,
    ):
        """Сервис запрещает отрицательную цену без участия API."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
        )

        with pytest.raises(ValidationError):
            TrackService.add_recording(
                release=album,
                recording=recording,
                user=artist_user,
                price=Decimal('-10.00'),
            )

        assert not album.tracks.exists()

    def test_schedules_archive_after_commit(
        self,
        artist_user,
        django_capture_on_commit_callbacks,
    ):
        """Пересборка архива планируется только после commit."""
        album = AlbumFactory(
            artist=artist_user.artist_profile,
            is_published=False,
        )
        recording = RecordingFactory(
            owner=artist_user.artist_profile,
            created_by=artist_user,
        )

        with patch.object(
            AlbumArchiveScheduler,
            'schedule_by_id',
        ) as mocked_schedule:
            with django_capture_on_commit_callbacks(execute=True):
                TrackService.add_recording(
                    release=album,
                    recording=recording,
                    user=artist_user,
                    price=Decimal('150.00'),
                )

                mocked_schedule.assert_not_called()

            mocked_schedule.assert_called_once_with(album.pk)
