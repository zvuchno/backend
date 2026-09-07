"""Фикстуры тестов для приложения users.

Модуль содержит набор переиспользуемых pytest-фикстур,
специфичных для данного приложения.

Используется для:
- создания тестовых объектов (модели, пользователи и т.д.);
- подготовки состояния базы данных;
- генерации входных данных для тестов;
- упрощения и устранения дублирования в тестах.

Файл не требует явного импорта — pytest находит его автоматически.
"""

from collections.abc import Callable
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from config import settings
from users.consents_policy import ConsentPolicy, ConsentScenario
from users.models import (
    ArtistProfile,
    ArtistProfileClaimInvitation,
    ConsentDocument,
    TokenInvitation,
    TokenInvitationStatus,
)
from users.services.invitation import hash_invitation_token
from users.tests.factories import (
    ArtistProfileFactory,
    LabelUserFactory,
    UserFactory,
)
from users.tests.helpers import create_artist_legal_profile


@pytest.fixture
def current_password():
    """Возвращает пароль тестового пользователя."""
    return 'CurrentPassword-482!'


@pytest.fixture
def password_user(current_password):
    """Создаёт пользователя с установленным известным паролем."""
    user = UserFactory()
    user.set_password(current_password)
    user.save(update_fields=['password'])
    return user


@pytest.fixture
def artist_legal_profile_factory():
    """Создаёт юридический профиль артиста."""
    return create_artist_legal_profile


@pytest.fixture
def legal_profile_payload():
    """Payload юридического профиля."""
    return {
        'legal_profile': {
            'email': 'legal1@artist.ru',
            'phone': '+79991234567',
            'recipient_type': 'self_employed',
        },
    }


@pytest.fixture
def identity_data_payload():
    """Payload паспортных данных."""
    return {
        'identity_data': {
            'first_name': 'Иван1',
            'last_name': 'Иванов1',
            'middle_name': 'Иванович1',
            'birth_date': '1990-12-01',
            'registration_address': 'г. Москва1',
            'passport_series': '0001',
            'passport_number': '000001',
            'passport_issued_by': '111111',
            'passport_issue_date': '2010-12-01',
            'inn': '123456789011',
        },
    }


@pytest.fixture
def bank_data_payload():
    """Payload банковских данных."""
    return {
        'bank_data': {
            'bank_name': 'Тест-Банк1',
            'bik': '123456781',
            'correspondent_account': '12345678901234567891',
            'checking_account': '12345678901234567891',
        },
    }


@pytest.fixture
def company_data_payload():
    """Payload данных юридического лица."""
    return {
        'company_data': {
            'company_name': 'ООО Тест1',
            'company_address': 'г. Москва1',
            'inn': '1234567891',
            'ogrn': '1234567890121',
        },
    }


@pytest.fixture
def artist_register_payload(artist_registration_consents):
    """Payload регистрации артиста."""
    return {
        'username': 'artist_username',
        'email': 'artist@newmail.ru',
        'phone': '+79991234567',
        'password': 'qwertyhgfdsa123',
        'name': 'my rock band',
        'consents': artist_registration_consents,
    }


@pytest.fixture
def listener_register_payload(listener_registration_consents):
    """Payload регистрации слушателя."""
    return {
        'username': 'listener_username',
        'email': 'listener@newmail.ru',
        'phone': '+79991234567',
        'password': 'qwertyhgfdsa123',
        'consents': listener_registration_consents,
    }


@pytest.fixture
def artist_claim_factory() -> Callable[..., tuple]:
    """Создаёт приглашение и возвращает его вместе с исходным токеном."""

    def create(
        *,
        artist=None,
        label_user=None,
        email='invited@test.local',
        token='test-invitation-token',
        status=TokenInvitationStatus.PENDING,
        expires_at=None,
    ) -> tuple[ArtistProfileClaimInvitation, str]:
        label_user = label_user or LabelUserFactory()

        if artist is None:
            artist = ArtistProfileFactory(
                user=None,
                label=label_user.artist_profile,
            )

        invitation = TokenInvitation.objects.create(
            recipient_email=email,
            token_hash=hash_invitation_token(token),
            status=status,
            created_by=label_user,
            expires_at=(
                expires_at
                or timezone.now()
                + timedelta(days=settings.INVITATION_TTL_DAYS)
            ),
        )

        claim = ArtistProfileClaimInvitation.objects.create(
            invitation=invitation,
            artist=artist,
        )

        return claim, token

    return create


@pytest.fixture
def listener_registration_consents():
    """Создаёт документы и возвращает согласия регистрации слушателя."""
    document_types = ConsentPolicy.get_required(
        ConsentScenario.LISTENER_REGISTRATION,
    )

    for document_type in document_types:
        ConsentDocument.objects.create(
            document_type=document_type,
            version='1.0',
            content=f'Тестовый документ: {document_type}',
            is_active=True,
        )

    return list(document_types)


@pytest.fixture
def artist_registration_consents():
    """Создаёт документы и возвращает обязательные согласия артиста."""
    document_types = ConsentPolicy.get_required(
        ConsentScenario.ARTIST_REGISTRATION,
    )

    for document_type in document_types:
        ConsentDocument.objects.create(
            document_type=document_type,
            version='1.0',
            content=f'Тестовый документ: {document_type}',
            is_active=True,
        )

    return list(document_types)


@pytest.fixture
def artist_onboarding_consents():
    """Создаёт документы и возвращает обязательные согласия артиста."""
    document_types = ConsentPolicy.get_required(
        ConsentScenario.ARTIST_ONBOARDING,
    )

    for document_type in document_types:
        ConsentDocument.objects.create(
            document_type=document_type,
            version='1.0',
            content=f'Тестовый документ: {document_type}',
            is_active=True,
        )

    return list(document_types)


# =================================
# URL fixtures
# =================================


@pytest.fixture
def artist_legal_url():
    """URL юридических данных артиста."""
    return reverse('api:users:artist_legal_profile')


@pytest.fixture
def artist_recipient_type_url():
    """URL справочника типа получателей."""
    return reverse('api:users:recipient_type_list')


@pytest.fixture
def listener_register_url():
    """URL регистрации слушателя."""
    return reverse('api:users:listener_registration')


@pytest.fixture
def artist_register_url():
    """URL регистрации артиста."""
    return reverse('api:users:artist_registration')


@pytest.fixture
def reset_password_url():
    """URL восстановления пароля."""
    return reverse('api:users:reset_password')


@pytest.fixture
def resend_email_verification_url():
    """URL повторного подтверждения email."""
    return reverse('api:users:resend_verification_email')


@pytest.fixture
def account_set_password_url():
    """URL установки первого пароля."""
    return reverse('api:users:set_password')


@pytest.fixture
def change_password_url():
    """URL смены установленного пароля."""
    return reverse('api:users:change_password')


@pytest.fixture
def reset_password_verify_url():
    """URL проверки ссылки сброса пароля."""
    return reverse('api:users:reset_password_verify')


@pytest.fixture
def reset_password_confirm_url():
    """URL подтверждения сброса пароля."""
    return reverse('api:users:reset_password_confirm')


@pytest.fixture
def account_me_url():
    """URL данных текущей учетной записи."""
    return reverse('api:users:me')


@pytest.fixture
def become_artist_url():
    """URL создания профиля артиста или лейбла."""
    return reverse('api:users:become_artist')


@pytest.fixture
def artist_me_url():
    """URL профиля текущего артиста или лейбла."""
    return reverse('api:users:artist_me')


@pytest.fixture
def artist_public_url():
    """Возвращает URL публичного профиля артиста или лейбла."""

    def build_url(profile: ArtistProfile) -> str:
        return reverse(
            'api:users:artist_public',
            kwargs={'slug': profile.slug},
        )

    return build_url


@pytest.fixture
def label_managed_profiles_url() -> str:
    """Возвращает URL списка управляемых профилей."""
    return reverse('api:users:label_managed_profiles')


@pytest.fixture
def managed_pickup_point_list_url():
    """Возвращает URL списка точек самовывоза управляемого профиля."""

    def build(profile) -> str:
        return reverse(
            'api:users:managed_profile_pickup_point_list',
            kwargs={'profile_id': profile.id},
        )

    return build


@pytest.fixture
def managed_pickup_point_detail_url():
    """Возвращает URL точки самовывоза управляемого профиля."""

    def build(profile, pickup_point) -> str:
        return reverse(
            'api:users:managed_profile_pickup_point_detail',
            kwargs={
                'profile_id': profile.id,
                'pk': pickup_point.id,
            },
        )

    return build


@pytest.fixture
def managed_shipping_point_url():
    """Возвращает URL ПВЗ отправления управляемого профиля."""

    def build(profile) -> str:
        return reverse(
            'api:users:managed_profile_shipping_point',
            kwargs={'profile_id': profile.id},
        )

    return build


@pytest.fixture
def artist_me_pickup_point_list_url() -> str:
    """Возвращает URL точек самовывоза собственного профиля."""
    return reverse('api:users:artist_me_pickup_point_list')


@pytest.fixture
def artist_me_pickup_point_detail_url():
    """Возвращает URL точки самовывоза собственного профиля."""

    def build(pickup_point) -> str:
        return reverse(
            'api:users:artist_me_pickup_point_detail',
            kwargs={'pk': pickup_point.id},
        )

    return build


@pytest.fixture
def artist_me_shipping_point_url() -> str:
    """Возвращает URL ПВЗ отправления собственного профиля."""
    return reverse('api:users:artist_me_shipping_point')


@pytest.fixture
def managed_profile_detail_url():
    """Возвращает URL управляемого профиля."""

    def build(profile) -> str:
        return reverse(
            'api:users:managed_profile_detail',
            kwargs={'profile_id': profile.id},
        )

    return build


@pytest.fixture
def artist_me_store_settings_url() -> str:
    """Возвращает URL настроек магазина собственного профиля."""
    return reverse('api:users:artist_store_settings')


@pytest.fixture
def managed_store_settings_url():
    """Возвращает URL настроек магазина управляемого профиля."""

    def build(profile) -> str:
        return reverse(
            'api:users:managed_artist_store_settings',
            kwargs={'profile_id': profile.id},
        )

    return build


@pytest.fixture
def artist_claim_read_url() -> str:
    """Возвращает URL просмотра приглашения."""
    return reverse('api:users:artist_profile_claim_view')


@pytest.fixture
def artist_claim_accept_url() -> str:
    """Возвращает URL принятия приглашения."""
    return reverse('api:users:artist_profile_claim_accept')


@pytest.fixture
def artist_claim_reject_url() -> str:
    """Возвращает URL отклонения приглашения."""
    return reverse('api:users:artist_profile_claim_reject')


@pytest.fixture
def managed_artist_claim_create_url() -> Callable[[ArtistProfile], str]:
    """Возвращает builder URL создания приглашения."""

    def build(profile) -> str:
        """Строит URL создания приглашения."""
        return reverse(
            'api:users:managed_profile_claim_invitation_create',
            kwargs={'profile_id': profile.id},
        )

    return build


@pytest.fixture
def managed_artist_claim_resend_url() -> Callable[[ArtistProfile], str]:
    """Возвращает builder URL повторной отправки приглашения."""

    def build(profile) -> str:
        """Строит URL повторной отправки приглашения."""
        return reverse(
            'api:users:managed_profile_claim_invitation_resend',
            kwargs={'profile_id': profile.id},
        )

    return build


@pytest.fixture
def managed_artist_claim_revoke_url() -> Callable[[ArtistProfile], str]:
    """Возвращает builder URL отзыва приглашения."""

    def build(profile) -> str:
        """Строит URL отзыва приглашения."""
        return reverse(
            'api:users:managed_profile_claim_invitation_revoke',
            kwargs={'profile_id': profile.id},
        )

    return build


@pytest.fixture
def verify_email_code_url():
    """URL подтверждения email по коду."""
    return reverse('api:users:verify_email_code')


@pytest.fixture
def verify_email_url():
    """URL подтверждения email по ссылке."""
    return reverse('api:users:verify_email')
