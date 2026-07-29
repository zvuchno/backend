from rest_framework.exceptions import PermissionDenied, ValidationError

from common.access import can_manage_artist

from users.models import ArtistProfile, ArtistProfileType


class ManagedArtistActionMixin:
    """Миксин для действий от имени управляемого артиста."""

    def _resolve_create_artist(self, serializer) -> ArtistProfile:
        """Определяет артиста создаваемого объекта."""
        validated_data = serializer.validated_data

        album = validated_data.get('album')
        if album is not None:
            return album.artist

        artist = validated_data.get('artist')
        if artist is not None:
            return artist

        profile = getattr(
            self.request.user,
            'artist_profile',
            None,
        )

        if profile is None or profile.profile_type != ArtistProfileType.ARTIST:
            raise ValidationError({
                'artist': 'Необходимо указать профиль артиста или лейбла.',
            })

        return profile

    def _get_managed_artist(self, serializer) -> ArtistProfile:
        """Возвращает артиста после проверки права управления."""
        artist = self._resolve_create_artist(serializer)

        if not can_manage_artist(self.request.user, artist):
            raise PermissionDenied(
                'У вас нет прав управлять этим артистом.',
            )

        return artist
