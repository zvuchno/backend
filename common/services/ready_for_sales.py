from dataclasses import dataclass
from enum import StrEnum

from django.conf import settings
from django.db.models import Q

from users.models import ArtistProfile


class PublicationRequirement(StrEnum):
    """Причины недоступности публикации."""

    EMAIL_VERIFICATION = 'email_verification'
    LEGAL_PROFILE_VERIFICATION = 'legal_profile_verification'
    SHIPPING_POINT = 'shipping_point'

    @property
    def description(self) -> str:
        """Возвращает краткое описание причины."""
        descriptions = {
            self.EMAIL_VERIFICATION: 'не подтверждён email',
            self.LEGAL_PROFILE_VERIFICATION: (
                'не подтверждены юридические данные'
            ),
            self.SHIPPING_POINT: (
                'Включите доставку СДЭК для публикации физических товаров.'
            ),
        }
        return descriptions[self]

    @property
    def publication_error_message(self) -> str:
        """Возвращает подсказку для устранения блокировки публикации."""
        messages = {
            self.EMAIL_VERIFICATION: (
                'Подтвердите email для публикации товаров.'
            ),
            self.LEGAL_PROFILE_VERIFICATION: (
                'Заполните раздел «Данные» в личном кабинете '
                'и дождитесь их подтверждения администратором.'
            ),
            self.SHIPPING_POINT: (
                'Укажите в настройках пункт СДЭК '
                'для отправки физических товаров.'
            ),
        }
        return messages[self]


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
    if not settings.PUBLICATION_READINESS_ENABLED:
        return ArtistPublicationReadiness(
            digital_missing=(),
            physical_missing=(),
        )
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


def digital_publication_ready_q(prefix: str = '') -> Q:
    """Возвращает условие готовности цифрового товара к публикации."""
    if not settings.PUBLICATION_READINESS_ENABLED:
        return Q()

    payout_recipient = f'{prefix}payout_recipient'

    return Q(
        **{
            f'{payout_recipient}__is_email_verified': True,
            f'{payout_recipient}__legal_profile__is_verified': True,
        },
    )


def physical_publication_ready_q(prefix: str = '') -> Q:
    """Возвращает условие готовности физического товара к публикации."""
    if not settings.PUBLICATION_READINESS_ENABLED:
        return Q()

    artist = f'{prefix}artist'

    own_shipping_q = Q(**{
        f'{artist}__store_settings__shipping_enabled': True,
    }) & _shipping_point_configured_q(
        f'{artist}__shipping_point',
    )

    label_shipping_q = (
        (
            Q(**{f'{artist}__store_settings__shipping_enabled': False})
            | Q(**{f'{artist}__store_settings__isnull': True})
        )
        & Q(
            **{
                f'{artist}__label__store_settings__shipping_enabled': True,
            },
        )
        & _shipping_point_configured_q(
            f'{artist}__label__shipping_point',
        )
    )

    return digital_publication_ready_q(prefix) & (
        own_shipping_q | label_shipping_q
    )


def artist_publication_ready_q(prefix: str = '') -> Q:
    """Возвращает условие готовности артиста к публичному отображению."""
    if not settings.PUBLICATION_READINESS_ENABLED:
        return Q()

    own_user_q = Q(
        **{
            f'{prefix}label__isnull': True,
            f'{prefix}user__is_email_verified': True,
            f'{prefix}user__legal_profile__is_verified': True,
        },
    )

    label_user_q = Q(
        **{
            f'{prefix}label__isnull': False,
            f'{prefix}label__user__is_email_verified': True,
            f'{prefix}label__user__legal_profile__is_verified': True,
        },
    )

    return own_user_q | label_user_q


def _shipping_point_configured_q(prefix: str) -> Q:
    """Проверяет наличие обязательных кодов ПВЗ СДЭК."""
    return Q(
        **{
            f'{prefix}__pvz_code__gt': '',
            f'{prefix}__city_code__gt': '',
        },
    )
