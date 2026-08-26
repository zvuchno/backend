"""Сервис фиксации пользовательских согласий."""

from collections.abc import Iterable

from rest_framework.exceptions import ValidationError

from users.consents_policy import ConsentContext, ConsentPolicy
from users.models import ConsentDocument, UserConsent


class ConsentService:
    """Проверяет и сохраняет пользовательские согласия."""

    @classmethod
    def accept(
        cls,
        *,
        context: ConsentContext,
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
            context=context,
            accepted_types=accepted_types,
        )

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
        context: ConsentContext,
        accepted_types: set[str],
    ) -> None:
        """Проверяет обязательные и допустимые типы согласий."""
        required = ConsentPolicy.get_required(context)
        allowed = ConsentPolicy.get_allowed(context)

        missing = required - accepted_types

        if missing:
            raise ValidationError({
                'consents': 'Не приняты все обязательные согласия.',
            })

        unknown = accepted_types - allowed

        if unknown:
            raise ValidationError({
                'consents': (
                    'Переданы согласия, недоступные для этого сценария.'
                ),
            })
