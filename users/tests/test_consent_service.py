"""Тесты пользовательских согласий."""

import pytest
from django.urls import reverse
from django.utils import timezone

from users.models import ConsentDocument, UserConsent
from users.services import ConsentService
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def create_consent_document(
    document_type,
    *,
    version='1.0',
    is_active=True,
):
    """Создаёт версию документа согласия."""
    return ConsentDocument.objects.create(
        document_type=document_type,
        version=version,
        content=f'Документ {document_type} {version}',
        is_active=is_active,
    )


def create_user_consent(
    *,
    document,
    user=None,
    email='listener@example.com',
    revoked_at=None,
):
    """Создаёт пользовательское согласие."""
    return UserConsent.objects.create(
        user=user,
        email=email,
        document=document,
        revoked_at=revoked_at,
    )


class TestConsentService:
    """Тесты сервиса пользовательских согласий."""

    def test_revoke_revokes_all_versions_of_document_type(self):
        """Отзывает все версии согласия одного типа."""
        user = UserFactory(email='listener@example.com')

        document_v1 = create_consent_document(
            ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
            version='1.0',
        )
        consent_v1 = create_user_consent(
            user=user,
            email=user.email,
            document=document_v1,
        )

        document_v1.is_active = False
        document_v1.save(update_fields=('is_active',))

        document_v2 = create_consent_document(
            ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
            version='2.0',
        )
        consent_v2 = create_user_consent(
            user=user,
            email=user.email,
            document=document_v2,
        )

        offer = create_consent_document(
            ConsentDocument.DocumentType.LISTENER_OFFER,
        )
        offer_consent = create_user_consent(
            user=user,
            email=user.email,
            document=offer,
        )

        revoked_count = ConsentService.revoke(
            document_type=document_v2.document_type,
            user=user,
            email=user.email,
        )

        consent_v1.refresh_from_db()
        consent_v2.refresh_from_db()
        offer_consent.refresh_from_db()

        assert revoked_count == 2
        assert consent_v1.is_revoked is True
        assert consent_v2.is_revoked is True
        assert offer_consent.is_revoked is False

    def test_revoke_user_also_revokes_anonymous_consents_by_email(self):
        """Отзывает связанные с пользователем и его email согласия."""
        user = UserFactory(email='listener@example.com')
        document = create_consent_document(
            ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
        )

        user_consent = create_user_consent(
            user=user,
            email=user.email,
            document=document,
        )
        anonymous_consent = create_user_consent(
            email=user.email,
            document=document,
        )
        other_consent = create_user_consent(
            email='other@example.com',
            document=document,
        )

        revoked_count = ConsentService.revoke(
            document_type=document.document_type,
            user=user,
            email=user.email,
        )

        user_consent.refresh_from_db()
        anonymous_consent.refresh_from_db()
        other_consent.refresh_from_db()

        assert revoked_count == 2
        assert user_consent.is_revoked is True
        assert anonymous_consent.is_revoked is True
        assert other_consent.is_revoked is False

    def test_revoke_does_not_update_already_revoked_consent(self):
        """Не изменяет дату ранее отозванного согласия."""
        user = UserFactory(email='listener@example.com')
        document = create_consent_document(
            ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
        )
        revoked_at = timezone.now()

        consent = create_user_consent(
            user=user,
            email=user.email,
            document=document,
            revoked_at=revoked_at,
        )

        revoked_count = ConsentService.revoke(
            document_type=document.document_type,
            user=user,
            email=user.email,
        )

        consent.refresh_from_db()

        assert revoked_count == 0
        assert consent.revoked_at == revoked_at

    def test_revoke_requires_user_or_email(self):
        """Не позволяет отзывать согласия без идентификатора."""
        with pytest.raises(
            ValueError,
            match='Для отзыва согласия нужен пользователь или email.',
        ):
            ConsentService.revoke(
                document_type=(
                    ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA
                ),
            )


class TestUserConsentAdmin:
    """Тесты админки пользовательских согласий."""

    def test_revoke_selected_consents(self, admin_client):
        """Admin action отзывает выбранные согласия."""
        user = UserFactory(email='listener@example.com')
        document = create_consent_document(
            ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
        )
        consent = create_user_consent(
            user=user,
            email=user.email,
            document=document,
        )

        response = admin_client.post(
            reverse('admin:users_userconsent_changelist'),
            {
                'action': 'revoke_selected_consents',
                '_selected_action': [consent.pk],
            },
            follow=True,
        )

        consent.refresh_from_db()

        assert response.status_code == 200
        assert consent.is_revoked is True
