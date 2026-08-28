"""Сервис фиксации пользовательских согласий."""

from collections.abc import Iterable

from django.conf import settings
from rest_framework.exceptions import ValidationError

from users.consents_policy import ConsentPolicy, ConsentScenario
from users.models import ConsentDocument, UserConsent


class ConsentService:
    """Проверяет и сохраняет пользовательские согласия."""

    @classmethod
    def accept(
        cls,
        *,
        scenario: ConsentScenario,
        accepted_types: Iterable[str],
        user,
        email: str,
        ip_address: str | None = None,
        user_agent: str = '',
        order=None,
        artist=None,
    ) -> None:
        """Фиксирует принятые пользователем согласия."""
        accepted_types = set(accepted_types)

        cls.validate(
            scenario=scenario,
            accepted_types=accepted_types,
        )

        if not accepted_types:
            return

        documents = ConsentDocument.objects.filter(
            document_type__in=accepted_types,
            is_active=True,
        )

        documents_by_type = {
            document.document_type: document for document in documents
        }

        missing_documents = accepted_types - documents_by_type.keys()

        if missing_documents:
            raise ValidationError({
                'consents': (
                    'Для одного или нескольких согласий '
                    'не найдена актуальная версия документа.'
                ),
            })

        for document_type in accepted_types:
            UserConsent.objects.create(
                user=user,
                email=email,
                document=documents_by_type[document_type],
                ip_address=ip_address,
                user_agent=user_agent,
                order=order,
                artist=artist,
            )

    @staticmethod
    def validate(
        *,
        scenario: ConsentScenario,
        accepted_types: set[str],
    ) -> None:
        """Проверяет обязательные типы согласий."""
        if not settings.CONSENT_ENFORCE_REQUIRED:
            return

        required = ConsentPolicy.get_required(scenario)
        missing = required - accepted_types

        if missing:
            raise ValidationError({
                'consents': 'Не приняты все обязательные согласия.',
                'missing': sorted(missing),
            })
