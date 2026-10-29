from store.models import Album, Recording
from users.models import ArtistProfile, ArtistProfileType


def _get_label_id(profile: ArtistProfile) -> int | None:
    """Возвращает идентификатор лейбла, к которому относится профиль."""
    if profile.profile_type == ArtistProfileType.LABEL:
        return profile.pk

    return profile.label_id


def can_use_recording_in_release(
    recording: Recording,
    release: Album,
) -> bool:
    """Проверяет совместимость владельца записи и артиста релиза."""
    if recording.owner_id == release.artist_id:
        return True

    recording_label_id = _get_label_id(recording.owner)
    release_label_id = _get_label_id(release.artist)

    return (
        recording_label_id is not None
        and recording_label_id == release_label_id
    )
