from django.db import transaction

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

        return ReleaseTrack.objects.create(
            release=release,
            recording=recording,
        )
