from dataclasses import dataclass
from enum import StrEnum

from users.models import ArtistProfile


class PublicationRequirement(StrEnum):
    """Причины недоступности публикации."""

    EMAIL_VERIFICATION = 'email_verification'
    LEGAL_PROFILE_VERIFICATION = 'legal_profile_verification'
    SHIPPING_POINT = 'shipping_point'


@dataclass(frozen=True)
class ArtistPublicationReadiness:
    """Состояние готовности артиста к публикации товаров."""

    digital_missing: tuple[PublicationRequirement, ...]
    physical_missing: tuple[PublicationRequirement, ...]

    @property
    def can_publish_digital(self) -> bool:
        """Можно ли публиковать цифровые товары."""
        return not self.digital_missing

    @property
    def can_publish_physical(self) -> bool:
        """Можно ли публиковать физические товары."""
        return not self.physical_missing


def get_artist_publication_readiness(
    artist: ArtistProfile,
) -> ArtistPublicationReadiness:
    """Возвращает готовность артиста к публикации товаров."""
    payout_recipient = artist.default_payout_recipient

    digital_missing = []

    if not payout_recipient.is_email_verified:
        digital_missing.append(
            PublicationRequirement.EMAIL_VERIFICATION,
        )

    legal_profile = getattr(payout_recipient, 'legal_profile', None)
    if legal_profile is None or not legal_profile.is_verified:
        digital_missing.append(
            PublicationRequirement.LEGAL_PROFILE_VERIFICATION,
        )

    physical_missing = list(digital_missing)

    if artist.effective_shipping_point is None:
        physical_missing.append(
            PublicationRequirement.SHIPPING_POINT,
        )

    return ArtistPublicationReadiness(
        digital_missing=tuple(digital_missing),
        physical_missing=tuple(physical_missing),
    )
