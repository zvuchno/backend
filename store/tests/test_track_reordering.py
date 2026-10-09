from unittest import mock

import pytest
from rest_framework import status

from store.models import AlbumArchive
from store.services.album_archive import (
    AlbumArchiveScheduler,
    AlbumArchiveService,
)
from store.services.track import reorder_tracks
from store.tests.factories import AlbumFactory, TrackFactory

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
    """Три активных трека с позициями 1, 2, 3."""
    return [
        TrackFactory(album=album, position=position) for position in (1, 2, 3)
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
        other_track = TrackFactory(position=1)
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
        deleted = TrackFactory(album=album, position=4, is_active=False)

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
        a, b = (TrackFactory(album=album, position=p) for p in (1, 2))

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

    def test_rolls_back_positions_if_scheduler_fails(self, album, tracks):
        """Ошибка планировщика откатывает изменение позиций."""
        before = db_order(album)

        with mock.patch.object(
            AlbumArchiveScheduler,
            'schedule_by_id',
            side_effect=RuntimeError,
        ):
            with pytest.raises(RuntimeError):
                reorder_tracks(album, [t.id for t in reversed(tracks)])

        assert db_order(album) == before
