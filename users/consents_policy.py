"""Политика обязательных и доступных пользовательских согласий."""

from enum import StrEnum

from users.models import ConsentDocument


class ConsentScenario(StrEnum):
    """Пользовательские сценарии для согласий."""

    LISTENER_REGISTRATION = 'listener_registration'
    ARTIST_REGISTRATION = 'artist_registration'
    LABEL_REGISTRATION = 'label_registration'
    ARTIST_ONBOARDING = 'artist_onboarding'
    LABEL_ONBOARDING = 'label_onboarding'
    CHECKOUT = 'checkout'


class ConsentPolicy:
    """Определяет набор согласий для пользовательского сценария."""

    REQUIRED = {
        ConsentScenario.LISTENER_REGISTRATION: frozenset({
            ConsentDocument.DocumentType.LISTENER_OFFER,
            ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
            ConsentDocument.DocumentType.LISTENER_DISTRIBUTION,
        }),
        ConsentScenario.ARTIST_REGISTRATION: frozenset({
            ConsentDocument.DocumentType.LISTENER_OFFER,
            ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
            ConsentDocument.DocumentType.LISTENER_DISTRIBUTION,
            ConsentDocument.DocumentType.ARTIST_OFFER,
            ConsentDocument.DocumentType.ARTIST_PERSONAL_DATA,
            ConsentDocument.DocumentType.ARTIST_DISTRIBUTION,
        }),
        ConsentScenario.LABEL_REGISTRATION: frozenset({
            ConsentDocument.DocumentType.LISTENER_OFFER,
            ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
            ConsentDocument.DocumentType.LISTENER_DISTRIBUTION,
            ConsentDocument.DocumentType.ARTIST_OFFER,
            ConsentDocument.DocumentType.ARTIST_PERSONAL_DATA,
            ConsentDocument.DocumentType.ARTIST_DISTRIBUTION,
        }),
        ConsentScenario.ARTIST_ONBOARDING: frozenset({
            ConsentDocument.DocumentType.ARTIST_OFFER,
            ConsentDocument.DocumentType.ARTIST_PERSONAL_DATA,
            ConsentDocument.DocumentType.ARTIST_DISTRIBUTION,
        }),
        ConsentScenario.LABEL_ONBOARDING: frozenset({
            ConsentDocument.DocumentType.ARTIST_OFFER,
            ConsentDocument.DocumentType.ARTIST_PERSONAL_DATA,
            ConsentDocument.DocumentType.ARTIST_DISTRIBUTION,
        }),
        ConsentScenario.CHECKOUT: frozenset({
            ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
        }),
    }

    OPTIONAL = {
        ConsentScenario.LISTENER_REGISTRATION: frozenset({
            ConsentDocument.DocumentType.LISTENER_NEWSLETTER,
        }),
        ConsentScenario.ARTIST_REGISTRATION: frozenset({
            ConsentDocument.DocumentType.LISTENER_NEWSLETTER,
            ConsentDocument.DocumentType.ARTIST_NEWSLETTER,
        }),
        ConsentScenario.LABEL_REGISTRATION: frozenset({
            ConsentDocument.DocumentType.LISTENER_NEWSLETTER,
            ConsentDocument.DocumentType.ARTIST_NEWSLETTER,
        }),
        ConsentScenario.ARTIST_ONBOARDING: frozenset({
            ConsentDocument.DocumentType.ARTIST_NEWSLETTER,
        }),
        ConsentScenario.LABEL_ONBOARDING: frozenset({
            ConsentDocument.DocumentType.ARTIST_NEWSLETTER,
        }),
    }

    @classmethod
    def get_required(
        cls,
        scenario: ConsentScenario,
    ) -> frozenset[str]:
        """Возвращает обязательные согласия для сценария."""
        return cls.REQUIRED.get(scenario, frozenset())

    @classmethod
    def get_optional(
        cls,
        scenario: ConsentScenario,
    ) -> frozenset[str]:
        """Возвращает необязательные согласия для сценария."""
        return cls.OPTIONAL.get(scenario, frozenset())

    @classmethod
    def get_requirements(cls) -> list[dict[str, str | list[str]]]:
        """Возвращает требования согласий для всех сценариев."""
        return [
            {
                'scenario': scenario.value,
                'required': sorted(cls.get_required(scenario)),
                'optional': sorted(cls.get_optional(scenario)),
            }
            for scenario in ConsentScenario
        ]
