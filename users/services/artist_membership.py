from django.db import transaction
from rest_framework.serializers import ValidationError

from store.models import Album, Merch
from users.models import ArtistProfile


class ArtistMembershipService:
    """Сервис управления связью артиста с лейблом.

    TODO: добавить к валидации is_verified артиста вместо email_is_verified,
    но не убирать legal_profile.is_verified.
    """

    @classmethod
    @transaction.atomic
    def leave_label(cls, *, artist: ArtistProfile) -> ArtistProfile:
        """Открепляет артиста от лейбла и передаёт ему выплаты."""
        artist = (
            ArtistProfile.objects
            .select_for_update(of=('self',))
            .select_related('user', 'user__legal_profile')
            .get(pk=artist.pk)
        )

        cls._validate_leave_label(artist)

        Album.objects.filter(
            artist=artist,
        ).update(
            payout_recipient=artist.user,
        )

        Merch.objects.filter(
            artist=artist,
        ).update(
            payout_recipient=artist.user,
        )

        artist.label = None
        artist.save(update_fields=('label', 'updated_at'))

        return artist

    @staticmethod
    def _validate_leave_label(artist: ArtistProfile) -> None:
        """Проверяет возможность самостоятельного выхода из лейбла."""
        if artist.label_id is None:
            raise ValidationError(
                'Артист не состоит в лейбле.',
            )

        if artist.user_id is None:
            raise ValidationError(
                'Для выхода из лейбла требуется учётная запись артиста.',
            )

        if not artist.user.is_email_verified:
            raise ValidationError(
                'Для выхода из лейбла необходимо подтвердить email.',
            )

        legal_profile = getattr(artist.user, 'legal_profile', None)

        if legal_profile is None or not legal_profile.is_verified:
            raise ValidationError(
                'Для выхода из лейбла нужно быть верифицированным артистом.',
            )
