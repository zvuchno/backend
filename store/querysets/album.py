from django.db import models
from django.db.models import Count, F, Q


class AlbumQuerySet(models.QuerySet):
    """QuerySet альбомов."""

    def fully_available_for_track_ids(self, track_ids):
        """Альбомы, для которых доступны все треки."""
        return (
            self
            .annotate(
                total_tracks=Count('tracks', distinct=True),
                available_tracks=Count(
                    'tracks',
                    filter=Q(tracks__id__in=track_ids),
                    distinct=True,
                ),
            )
            .filter(
                total_tracks=F('available_tracks'),
                total_tracks__gt=0,
                available_tracks__gt=0,
            )
            .distinct()
            .prefetch_related('tracks')
        )
