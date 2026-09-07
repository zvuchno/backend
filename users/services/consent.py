"""Сервис фиксации пользовательских согласий."""

from collections.abc import Iterable

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
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
        skip_existing: bool = False,
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

        existing_document_ids = set()

        if skip_existing and user is not None:
            existing_document_ids = set(
                UserConsent.objects.filter(
                    user=user,
                    document__in=documents_by_type.values(),
                    revoked_at__isnull=True,
                ).values_list(
                    'document_id',
                    flat=True,
                ),
            )

        for document_type in accepted_types:
            document = documents_by_type[document_type]
            if document.id in existing_document_ids:
                continue

            UserConsent.objects.create(
                user=user,
                email=email,
                document=documents_by_type[document_type],
                ip_address=ip_address,
                user_agent=user_agent,
                order=order,
                artist=artist,
            )

    @classmethod
    def revoke(
        cls,
        *,
        document_type: str,
        user=None,
        email: str | None = None,
    ) -> int:
        """Отзывает действующие согласия указанного типа."""
        if user is None and not email:
            raise ValueError(
                'Для отзыва согласия нужен пользователь или email.',
            )

        queryset = UserConsent.objects.filter(
            document__document_type=document_type,
            revoked_at__isnull=True,
        )

        if user is not None:
            identity_q = Q(user=user)

            effective_email = email or user.email
            if effective_email:
                identity_q |= Q(
                    user__isnull=True,
                    email=effective_email,
                )

            queryset = queryset.filter(identity_q)
        else:
            queryset = queryset.filter(
                user__isnull=True,
                email=email,
            )

        return queryset.update(
            revoked_at=timezone.now(),
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
