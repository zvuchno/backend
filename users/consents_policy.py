"""Политика обязательных и доступных пользовательских согласий."""

from enum import StrEnum

from users.models import ConsentDocument


class ConsentContext(StrEnum):
    """Контекст, в котором пользователь принимает согласия."""

    LISTENER_REGISTRATION = 'listener_registration'
    ARTIST_ONBOARDING = 'artist_onboarding'
    LABEL_ONBOARDING = 'label_onboarding'
    CHECKOUT = 'checkout'


class ConsentPolicy:
    """Определяет набор согласий для пользовательского сценария."""

    REQUIRED = {
        ConsentContext.LISTENER_REGISTRATION: frozenset({
            ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
        }),
        ConsentContext.ARTIST_ONBOARDING: frozenset({
            ConsentDocument.DocumentType.ARTIST_OFFER,
            ConsentDocument.DocumentType.ARTIST_PERSONAL_DATA,
            ConsentDocument.DocumentType.ARTIST_DISTRIBUTION,
        }),
        ConsentContext.LABEL_ONBOARDING: frozenset({
            ConsentDocument.DocumentType.ARTIST_OFFER,
            ConsentDocument.DocumentType.ARTIST_PERSONAL_DATA,
            ConsentDocument.DocumentType.ARTIST_DISTRIBUTION,
        }),
        ConsentContext.CHECKOUT: frozenset({
            ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
        }),
    }

    OPTIONAL = {
        ConsentContext.ARTIST_ONBOARDING: frozenset({
            ConsentDocument.DocumentType.ARTIST_NEWSLETTER,
        }),
        ConsentContext.LABEL_ONBOARDING: frozenset({
            ConsentDocument.DocumentType.ARTIST_NEWSLETTER,
        }),
    }

    @classmethod
    def get_required(
        cls,
        context: ConsentContext,
    ) -> frozenset[str]:
        """Возвращает обязательные согласия для контекста."""
        return cls.REQUIRED.get(context, frozenset())

    @classmethod
    def get_optional(
        cls,
        context: ConsentContext,
    ) -> frozenset[str]:
        """Возвращает необязательные согласия для контекста."""
        return cls.OPTIONAL.get(context, frozenset())

    @classmethod
    def get_allowed(
        cls,
        context: ConsentContext,
    ) -> frozenset[str]:
        """Возвращает все допустимые согласия для контекста."""
        return cls.get_required(context) | cls.get_optional(context)
