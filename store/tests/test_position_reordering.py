from unittest import mock

import pytest
from django.db.models import QuerySet
from rest_framework import status

from store.models import AlbumArchive, Merch, ReleaseTrack
from store.services import reorder_objects
from store.services.album_archive import (
    AlbumArchiveScheduler,
    AlbumArchiveService,
)
from store.tests.factories import (
    AlbumFactory,
    BonusFactory,
    MerchFactory,
    ReleaseTrackFactory,
)

TASK_PATH = 'store.tasks.album_archive.build_album_archive.apply_async'


@pytest.fixture
def album(artist_user):
    """Создаёт опубликованный альбом артиста."""
    return AlbumFactory(
        artist=artist_user.artist_profile,
        is_published=True,
    )


@pytest.fixture
def tracks(album):
    """Три активных трека релиза с позициями 1, 2, 3."""
    return [
        ReleaseTrackFactory(
            release=album,
            position=position,
        )
        for position in (1, 2, 3)
    ]


def payload(album, tracks_order):
    """Формирует payload для изменения порядка треков."""
    return {'album': album.id, 'track_ids': [t.id for t in tracks_order]}


def db_order(album):
    """Возвращает ID активных треков альбома в порядке позиций."""
    return list(
        album.tracks
        .filter(is_active=True)
        .order_by('position')
        .values_list('id', flat=True),
    )


class TestTrackReorder:
    """Проверяет изменение порядка треков через API."""

    def test_reorders_tracks(
        self,
        artist_client,
        track_reorder_url,
        album,
        tracks,
    ):
        """Треки получают позиции согласно переданному порядку."""
        a, b, c = tracks
        response = artist_client.patch(
            track_reorder_url,
            payload(album, [c, a, b]),
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert [t['id'] for t in response.data] == [c.id, a.id, b.id]
        assert [t['position'] for t in response.data] == [1, 2, 3]
        assert 'is_favorite' in response.data[0]
        assert db_order(album) == [c.id, a.id, b.id]

    @pytest.mark.parametrize(
        'make_ids',
        [
            pytest.param(lambda t, other: [t[0].id, t[1].id], id='missing'),
            pytest.param(
                lambda t, other: [t[0].id, t[0].id, t[1].id, t[2].id],
                id='duplicate',
            ),
            pytest.param(
                lambda t, other: [t[0].id, t[1].id, t[2].id, other.id],
                id='foreign-track',
            ),
            pytest.param(lambda t, other: [], id='empty'),
            pytest.param(lambda t, other: [t[0].id, 'x', t[2].id], id='nan'),
        ],
    )
    def test_invalid_ids_return_400_and_keep_order(
        self,
        artist_client,
        track_reorder_url,
        album,
        tracks,
        make_ids,
    ):
        """Некорректный список ID отклоняется без изменения порядка."""
        other_track = ReleaseTrackFactory(position=1)
        before = db_order(album)

        response = artist_client.patch(
            track_reorder_url,
            {'album': album.id, 'track_ids': make_ids(tracks, other_track)},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert db_order(album) == before

    def test_inactive_track_is_not_required(
        self,
        artist_client,
        track_reorder_url,
        album,
        tracks,
    ):
        """Неактивный трек не требуется передавать при сортировке."""
        a, b, c = tracks
        deleted = ReleaseTrackFactory(
            release=album,
            position=4,
            is_active=False,
        )

        ok = artist_client.patch(
            track_reorder_url,
            payload(album, [b, c, a]),
            format='json',
        )
        bad = artist_client.patch(
            track_reorder_url,
            payload(album, [b, c, a, deleted]),
            format='json',
        )

        assert ok.status_code == status.HTTP_200_OK
        assert bad.status_code == status.HTTP_400_BAD_REQUEST

    def test_unknown_album_returns_400(
        self,
        artist_client,
        track_reorder_url,
        tracks,
    ):
        """Несуществующий альбом отклоняется с ошибкой валидации."""
        response = artist_client.patch(
            track_reorder_url,
            {'album': 999999, 'track_ids': [t.id for t in tracks]},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestTrackReorderPermissions:
    """Проверяет права доступа к изменению порядка треков."""

    def test_other_artist_cannot_reorder(
        self,
        other_artist_client,
        track_reorder_url,
        album,
        tracks,
    ):
        """Чужой альбом нельзя пересортировать."""
        before = db_order(album)
        response = other_artist_client.patch(
            track_reorder_url,
            payload(album, list(reversed(tracks))),
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert db_order(album) == before

    def test_label_can_reorder_signed_artist_album(
        self,
        label_client,
        signed_artist_user,
        track_reorder_url,
    ):
        """Лейбл может пересортировать альбом подписанного артиста."""
        album = AlbumFactory(artist=signed_artist_user.artist_profile)
        a, b = (ReleaseTrackFactory(release=album, position=p) for p in (1, 2))

        response = label_client.patch(
            track_reorder_url,
            payload(album, [b, a]),
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK


class TestTrackReorderArchive:
    """Проверяет пересборку архива после изменения порядка треков."""

    def test_reorder_schedules_archive_rebuild(
        self,
        django_capture_on_commit_callbacks,
        artist_client,
        track_reorder_url,
        album,
        tracks,
    ):
        """Изменение порядка ставит архив альбома на пересборку."""
        a, b, c = tracks
        bonuses = list(
            album.bonuses.filter(is_active=True).order_by('name', 'id'),
        )

        AlbumArchive.objects.create(
            album=album,
            status=AlbumArchive.Status.READY,
            content_hash=AlbumArchiveService.calculate_content_hash(
                album=album,
                tracks=tracks,
                bonuses=bonuses,
            ),
        )

        with mock.patch(TASK_PATH) as apply_async:
            with django_capture_on_commit_callbacks(execute=True):
                response = artist_client.patch(
                    track_reorder_url,
                    payload(album, [c, b, a]),
                    format='json',
                )

        assert response.status_code == status.HTTP_200_OK
        archive = AlbumArchive.objects.get(album=album)
        new_tracks = list(album.tracks.order_by('position', 'id'))
        expected_hash = AlbumArchiveService.calculate_content_hash(
            album=album,
            tracks=new_tracks,
            bonuses=bonuses,
        )
        assert archive.status == AlbumArchive.Status.PENDING
        assert archive.pending_hash == expected_hash
        apply_async.assert_called_once()
        assert apply_async.call_args.kwargs['args'] == (
            album.id,
            expected_hash,
        )

    def test_same_order_does_not_schedule(
        self,
        django_capture_on_commit_callbacks,
        artist_client,
        track_reorder_url,
        album,
        tracks,
    ):
        """Неизменившийся порядок не запускает пересборку архива."""
        bonuses = list(
            album.bonuses.filter(is_active=True).order_by('name', 'id'),
        )

        AlbumArchive.objects.create(
            album=album,
            status=AlbumArchive.Status.READY,
            content_hash=AlbumArchiveService.calculate_content_hash(
                album=album,
                tracks=tracks,
                bonuses=bonuses,
            ),
        )

        with mock.patch(TASK_PATH) as apply_async:
            with django_capture_on_commit_callbacks(execute=True):
                artist_client.patch(
                    track_reorder_url,
                    payload(album, tracks),
                    format='json',
                )

        apply_async.assert_not_called()


class TestReorderTracksService:
    """Проверяет сервис изменения порядка треков."""

    def test_rolls_back_positions_if_update_fails(self, album, tracks):
        """Ошибка после записи позиций откатывает изменение."""
        before = db_order(album)
        real_bulk_update = QuerySet.bulk_update

        def update_then_fail(self, *args, **kwargs) -> None:
            real_bulk_update(self, *args, **kwargs)
            raise RuntimeError

        with mock.patch.object(
            QuerySet,
            'bulk_update',
            update_then_fail,
        ):
            with pytest.raises(RuntimeError):
                reorder_objects(
                    ReleaseTrack.objects.filter(release=album, is_active=True),
                    [t.id for t in reversed(tracks)],
                    'ids_field',
                )

        assert db_order(album) == before

    def test_schedules_archive_after_commit(
        self,
        artist_client,
        track_reorder_url,
        album,
        tracks,
        django_capture_on_commit_callbacks,
    ):
        """Проверяет перестроение архива после коммита транзакции."""
        with mock.patch.object(
            AlbumArchiveScheduler,
            'schedule_by_id',
        ) as schedule:
            with django_capture_on_commit_callbacks(execute=True):
                response = artist_client.patch(
                    track_reorder_url,
                    payload(album, list(reversed(tracks))),
                    format='json',
                )

        assert response.status_code == 200
        schedule.assert_called_once_with(album.pk)

    def test_does_not_schedule_archive_on_invalid_ids(
        self,
        artist_client,
        track_reorder_url,
        album,
        tracks,
        django_capture_on_commit_callbacks,
    ):
        """Проверяет, что архив не перестраивается при некорректных ID."""
        bad_payload = {'album': album.id, 'track_ids': [999999]}

        with mock.patch.object(
            AlbumArchiveScheduler,
            'schedule_by_id',
        ) as schedule:
            with django_capture_on_commit_callbacks(execute=True):
                response = artist_client.patch(
                    track_reorder_url,
                    bad_payload,
                    format='json',
                )

        assert response.status_code == 400
        schedule.assert_not_called()


class TestBonusReorder:
    """Тесты для изменения порядка бонусов альбома."""

    def test_reorders_bonuses(self, artist_client, album, bonuses_reorder_url):
        """Успешное изменение порядка бонусов альбома."""
        b1, b2 = (
            BonusFactory(album=album, position=1),
            BonusFactory(album=album, position=2),
        )

        response = artist_client.patch(
            bonuses_reorder_url,
            {'album': album.id, 'bonus_ids': [b2.id, b1.id]},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert list(
            album.bonuses.order_by('position').values_list('id', flat=True),
        ) == [b2.id, b1.id]

    def test_other_artist_cannot_reorder_bonuses(
        self,
        other_artist_client,
        album,
        bonuses_reorder_url,
    ):
        """Чужой артист не может менять порядок бонусов чужого альбома."""
        b1, b2 = (
            BonusFactory(album=album, position=1),
            BonusFactory(album=album, position=2),
        )

        response = other_artist_client.patch(
            bonuses_reorder_url,
            {'album': album.id, 'bonus_ids': [b2.id, b1.id]},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        b1.refresh_from_db()
        b2.refresh_from_db()

        assert b1.position == 1
        assert b2.position == 2


class TestMerchReorder:
    """Тесты для изменения порядка мерча."""

    def test_reorders_merch(
        self,
        artist_client,
        artist_user,
        merch_reorder_url,
    ):
        """Успешное изменение порядка мерча артиста."""
        artist = artist_user.artist_profile
        m1, m2 = (
            MerchFactory(artist=artist, position=1),
            MerchFactory(artist=artist, position=2),
        )

        response = artist_client.patch(
            merch_reorder_url,
            {'artist': artist.id, 'merch_ids': [m2.id, m1.id]},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert list(
            Merch.objects
            .filter(artist=artist)
            .order_by('position')
            .values_list('id', flat=True),
        ) == [m2.id, m1.id]

    def test_merch_duplicate_ids_returns_400(
        self,
        artist_client,
        artist_user,
        merch_reorder_url,
    ):
        """Дублирующиеся ID мерча вызывают ошибку валидации."""
        artist = artist_user.artist_profile
        m1 = MerchFactory(artist=artist, position=1)

        response = artist_client.patch(
            merch_reorder_url,
            {'artist': artist.id, 'merch_ids': [m1.id, m1.id]},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
