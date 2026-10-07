"""Сервисы для работы с треками."""

from django.db import transaction
from rest_framework import serializers

from store.models import Track
from store.services.album_archive import AlbumArchiveScheduler


def reorder_tracks(album, track_ids):
    """Атомарно расставляет позиции треков по порядку списка."""
    with transaction.atomic():
        tracks = Track.objects.select_for_update().filter(
            album=album,
            is_active=True,
        )
        by_id = {track.pk: track for track in tracks}

        if set(track_ids) != by_id.keys():
            raise serializers.ValidationError(
                {
                    'track_ids': 'Нужно передать все треки'
                    'альбома по одному разу.',
                },
            )

        for position, track_id in enumerate(track_ids, start=1):
            by_id[track_id].position = position

        Track.objects.bulk_update(by_id.values(), ['position'])
        AlbumArchiveScheduler.schedule_by_id(album.pk)
