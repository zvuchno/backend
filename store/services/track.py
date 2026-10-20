from django.db import transaction
from django.db.models import Max

from store.models import Album, Recording, ReleaseTrack
from store.validators import validate_isrc_format


class TrackService:
    """Операции над треками релиза."""

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        release: Album,
        created_by,
        name: str,
        description: str = '',
        audio_file=None,
        isrc: str | None = None,
    ) -> ReleaseTrack:
        """Создаёт новую запись и её первое размещение в релизе."""
        isrc = isrc or None

        if isrc is not None:
            validate_isrc_format(isrc)

        release = Album.objects.select_for_update().get(pk=release.pk)

        recording_data = {
            'owner': release.artist,
            'created_by': created_by,
            'name': name,
            'description': description,
            'isrc': isrc,
        }

        if audio_file is not None:
            recording_data['audio_file'] = audio_file

        recording = Recording.objects.create(**recording_data)

        last_position = (
            ReleaseTrack.objects.filter(
                release=release,
                position__isnull=False,
            ).aggregate(
                max_position=Max('position'),
            )
        )['max_position']

        return ReleaseTrack.objects.create(
            release=release,
            recording=recording,
            position=(last_position or 0) + 1,
        )
