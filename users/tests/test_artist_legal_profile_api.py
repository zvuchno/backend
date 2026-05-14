"""Тесты API юридических данных артиста.

TODO валидация.
"""

import pytest
from rest_framework import status
from rest_framework.response import Response

from users.models import (
    ArtistBankData,
    ArtistCompanyData,
    ArtistIdentityData,
    ArtistLegalProfile,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def patch_legal_profile(artist_client, artist_legal_url):
    """PATCH юридических данных артиста."""

    def _patch(payload) -> Response:
        return artist_client.patch(
            artist_legal_url,
            data=payload,
            format='json',
        )

    return _patch


class TestArtistLegalProfileGet:
    """Тесты получения юридических данных артиста."""

    def test_artist_can_get_non_existent_legal_profile_with_fields(
        self,
        artist_user,
        artist_client,
        artist_legal_url,
    ):
        """Артист получит не пустой объект при отсутствии юр профиля."""
        artist_user.phone = '+71234560000'
        artist_user.save(update_fields=['phone'])

        response = artist_client.get(artist_legal_url)

        assert response.status_code == status.HTTP_200_OK
        assert 'legal_profile' in response.data
        assert 'identity_data' in response.data
        assert 'bank_data' in response.data
        assert 'company_data' in response.data
        assert response.data['legal_profile']['email'] == artist_user.email
        assert response.data['legal_profile']['phone'] == str(
            artist_user.phone,
        )
        assert not ArtistLegalProfile.objects.filter(user=artist_user).exists()

    def test_artist_can_get_existent_legal_profile(
        self,
        artist_user,
        artist_client,
        artist_legal_url,
        artist_legal_profile_factory,
    ):
        """Артист получает существующий профиль."""
        legal_profile = artist_legal_profile_factory(user=artist_user)

        response = artist_client.get(artist_legal_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['legal_profile']['email'] == legal_profile.email
        assert response.data['legal_profile']['recipient_type'] == (
            legal_profile.recipient_type
        )
        assert response.data['identity_data'] is not None
        assert response.data['bank_data'] is not None
        assert response.data['company_data'] is None
        assert (
            ArtistLegalProfile.objects.get(user=artist_user) == legal_profile
        )

    def test_other_artist_cannot_get_artist_legal_profile(
        self,
        artist_user,
        other_artist_user,
        artist_legal_profile_factory,
        other_artist_client,
        artist_legal_url,
    ):
        """Другой артист не получает чужие юридические данные."""
        legal_profile = artist_legal_profile_factory(user=artist_user)

        response = other_artist_client.get(artist_legal_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['legal_profile']['email'] != legal_profile.email
        assert (
            response.data['legal_profile']['email'] == other_artist_user.email
        )
        assert response.data['identity_data'] is None
        assert response.data['bank_data'] is None
        assert response.data['company_data'] is None

    def test_not_artist_cannot_get_artist_legal_profile(
        self,
        listener_client,
        artist_legal_url,
    ):
        """Не артист не может получить юр. профиль."""
        response = listener_client.get(artist_legal_url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_anon_cant_get_artist_legal_profile(
        self,
        api_client,
        artist_legal_url,
    ):
        """Анон не может получить юр данные."""
        response = api_client.get(artist_legal_url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRecipientTypeList:
    """Тесты справочника типов получателей."""

    def test_authenticated_user_can_get_recipient_types(
        self,
        auth_client,
        artist_recipient_type_url,
    ):
        """Аутентифицированный пользователь может получить типы получателей."""
        response = auth_client.get(artist_recipient_type_url)

        expected_types = [
            {'value': '', 'label': 'Не указано'},
            {'value': 'individual_entrepreneur', 'label': 'ИП'},
            {'value': 'self_employed', 'label': 'СМЗ'},
            {'value': 'legal_entity', 'label': 'Юридическое лицо'},
        ]

        assert response.status_code == status.HTTP_200_OK
        for item in expected_types:
            assert item in response.data

    def test_anonymous_cannot_get_recipient_types(
        self,
        api_client,
        artist_recipient_type_url,
    ):
        """Аноним не может получить типы получателей."""
        response = api_client.get(artist_recipient_type_url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestArtistLegalProfilePatchPermissions:
    """Тесты доступа к изменению юридических данных артиста."""

    def test_artist_can_patch_legal_profile(
        self,
        artist_user,
        legal_profile_payload,
        patch_legal_profile,
    ):
        """Артисту доступен patch."""
        response = patch_legal_profile(legal_profile_payload)
        legal_profile = ArtistLegalProfile.objects.get(user=artist_user)

        assert response.status_code == status.HTTP_200_OK
        assert (
            legal_profile.email
            == (legal_profile_payload['legal_profile']['email'])
        )
        assert (
            response.data['legal_profile']['email']
            == (legal_profile_payload['legal_profile']['email'])
        )

    def test_not_artist_cannot_patch_legal_profile(
        self,
        listener_client,
        artist_legal_url,
    ):
        """Слушателю не доступно изменение юр профиля."""
        response = listener_client.patch(artist_legal_url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_anon_cannot_patch_legal_profile(
        self,
        api_client,
        artist_legal_url,
    ):
        """Анону не доступно изменение юр. профиля."""
        response = api_client.patch(artist_legal_url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_put_is_not_allowed(
        self,
        artist_client,
        artist_legal_url,
    ):
        """Put запрещен."""
        response = artist_client.put(artist_legal_url, data={}, format='json')

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_is_not_allowed(
        self,
        artist_client,
        artist_legal_url,
    ):
        """Delete запрещен."""
        response = artist_client.delete(artist_legal_url)

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class TestArtistLegalProfilePatchCreate:
    """Тесты создания юридических данных через PATCH."""

    def test_patch_creates_legal_profile_if_not_exists(
        self,
        artist_user,
        legal_profile_payload,
        patch_legal_profile,
    ):
        """Создается юр профиль."""
        assert ArtistLegalProfile.objects.count() == 0

        response = patch_legal_profile(legal_profile_payload)
        legal_profile = ArtistLegalProfile.objects.get(user=artist_user)

        assert response.status_code == status.HTTP_200_OK
        assert ArtistLegalProfile.objects.filter(user=artist_user).exists()
        assert (
            legal_profile.email
            == (legal_profile_payload['legal_profile']['email'])
        )
        assert ArtistLegalProfile.objects.count() == 1

    def test_patch_creates_nested_identity_data_if_not_exists(
        self,
        artist_user,
        legal_profile_payload,
        identity_data_payload,
        patch_legal_profile,
    ):
        """Создаются персональные данные."""
        assert ArtistIdentityData.objects.count() == 0

        response = patch_legal_profile({
            **legal_profile_payload,
            **identity_data_payload,
        })
        legal_profile = ArtistLegalProfile.objects.get(user=artist_user)
        identity_data = ArtistIdentityData.objects.get(
            legal_profile=legal_profile,
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            ArtistIdentityData.objects.filter(
                legal_profile=legal_profile,
            ).count()
            == 1
        )
        assert (
            identity_data.first_name
            == response.data['identity_data']['first_name']
        )
        assert (
            identity_data.first_name
            == (identity_data_payload['identity_data']['first_name'])
        )
        assert (
            identity_data.passport_number
            == (identity_data_payload['identity_data']['passport_number'])
        )

    def test_patch_creates_nested_bank_data_if_not_exists(
        self,
        artist_user,
        legal_profile_payload,
        bank_data_payload,
        patch_legal_profile,
    ):
        """Создаются банковские данные."""
        assert ArtistBankData.objects.count() == 0

        response = patch_legal_profile({
            **legal_profile_payload,
            **bank_data_payload,
        })
        legal_profile = ArtistLegalProfile.objects.get(user=artist_user)
        bank_data = ArtistBankData.objects.get(legal_profile=legal_profile)

        assert response.status_code == status.HTTP_200_OK
        assert (
            ArtistBankData.objects.filter(
                legal_profile=legal_profile,
            ).count()
            == 1
        )
        assert bank_data.bank_name == response.data['bank_data']['bank_name']
        assert (
            bank_data.bank_name == bank_data_payload['bank_data']['bank_name']
        )
        assert (
            bank_data.checking_account
            == (bank_data_payload['bank_data']['checking_account'])
        )

    def test_patch_creates_nested_company_data_if_not_exists(
        self,
        artist_user,
        legal_profile_payload,
        company_data_payload,
        patch_legal_profile,
    ):
        """Создаются юр данные."""
        assert ArtistCompanyData.objects.count() == 0

        legal_profile_payload['legal_profile']['recipient_type'] = (
            ArtistLegalProfile.RecipientType.LEGAL_ENTITY
        )

        response = patch_legal_profile({
            **legal_profile_payload,
            **company_data_payload,
        })
        legal_profile = ArtistLegalProfile.objects.get(user=artist_user)
        company_data = ArtistCompanyData.objects.get(
            legal_profile=legal_profile,
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            ArtistCompanyData.objects.filter(
                legal_profile=legal_profile,
            ).count()
            == 1
        )
        assert (
            company_data.company_name
            == response.data['company_data']['company_name']
        )
        assert (
            company_data.company_name
            == (company_data_payload['company_data']['company_name'])
        )
        assert (
            company_data.ogrn == company_data_payload['company_data']['ogrn']
        )


class TestArtistLegalProfilePatchUpdate:
    """Тесты обновления юридических данных через PATCH."""

    def test_patch_updates_existing_legal_profile(
        self,
        artist_user,
        artist_legal_profile_factory,
        legal_profile_payload,
        patch_legal_profile,
    ):
        """Обновляется существующий юр. профиль."""
        legal_profile = artist_legal_profile_factory(user=artist_user)
        old_id = legal_profile.id

        response = patch_legal_profile(legal_profile_payload)
        legal_profile.refresh_from_db()

        assert response.status_code == status.HTTP_200_OK
        assert ArtistLegalProfile.objects.count() == 1
        assert legal_profile.id == old_id
        assert (
            legal_profile.email
            == (legal_profile_payload['legal_profile']['email'])
        )
        assert (
            response.data['legal_profile']['email']
            == (legal_profile_payload['legal_profile']['email'])
        )

    def test_patch_updates_existing_identity_data(
        self,
        artist_user,
        artist_legal_profile_factory,
        identity_data_payload,
        patch_legal_profile,
    ):
        """Обновляются существующие персональные данные."""
        legal_profile = artist_legal_profile_factory(user=artist_user)
        identity_data = legal_profile.identity_data
        old_id = identity_data.id

        response = patch_legal_profile(identity_data_payload)
        identity_data.refresh_from_db()

        assert response.status_code == status.HTTP_200_OK
        assert (
            ArtistIdentityData.objects.filter(
                legal_profile=legal_profile,
            ).count()
            == 1
        )
        assert identity_data.id == old_id
        assert (
            identity_data.first_name
            == (identity_data_payload['identity_data']['first_name'])
        )
        assert (
            response.data['identity_data']['first_name']
            == (identity_data_payload['identity_data']['first_name'])
        )

    def test_patch_updates_existing_bank_data(
        self,
        artist_user,
        artist_legal_profile_factory,
        bank_data_payload,
        patch_legal_profile,
    ):
        """Обновляются существующие банковские данные."""
        legal_profile = artist_legal_profile_factory(user=artist_user)
        bank_data = legal_profile.bank_data
        old_id = bank_data.id

        response = patch_legal_profile(bank_data_payload)
        bank_data.refresh_from_db()

        assert response.status_code == status.HTTP_200_OK
        assert (
            ArtistBankData.objects.filter(
                legal_profile=legal_profile,
            ).count()
            == 1
        )
        assert bank_data.id == old_id
        assert (
            bank_data.bank_name == bank_data_payload['bank_data']['bank_name']
        )
        assert (
            response.data['bank_data']['bank_name']
            == (bank_data_payload['bank_data']['bank_name'])
        )

    def test_patch_updates_existing_company_data(
        self,
        artist_user,
        artist_legal_profile_factory,
        company_data_payload,
        patch_legal_profile,
    ):
        """Обновляются существующие юр. данные."""
        legal_profile = artist_legal_profile_factory(
            user=artist_user,
            recipient_type=ArtistLegalProfile.RecipientType.LEGAL_ENTITY,
            with_company_data=True,
        )
        company_data = legal_profile.company_data
        old_id = company_data.id

        response = patch_legal_profile(company_data_payload)
        company_data.refresh_from_db()

        assert response.status_code == status.HTTP_200_OK
        assert (
            ArtistCompanyData.objects.filter(
                legal_profile=legal_profile,
            ).count()
            == 1
        )
        assert company_data.id == old_id
        assert (
            company_data.company_name
            == (company_data_payload['company_data']['company_name'])
        )
        assert (
            response.data['company_data']['company_name']
            == (company_data_payload['company_data']['company_name'])
        )


class TestArtistLegalProfilePatchRules:
    """Тесты бизнес-правил изменения юридических данных."""

    def test_patch_does_not_clear_unpatched_nested_data(
        self,
        artist_user,
        artist_legal_profile_factory,
        legal_profile_payload,
        patch_legal_profile,
    ):
        """Не очищаются не переданные данные."""
        legal_profile = artist_legal_profile_factory(
            user=artist_user,
            recipient_type=ArtistLegalProfile.RecipientType.LEGAL_ENTITY,
            with_company_data=True,
        )
        old_phone = legal_profile.phone
        old_first_name = legal_profile.identity_data.first_name
        old_bank_name = legal_profile.bank_data.bank_name
        old_company_name = legal_profile.company_data.company_name

        legal_profile_payload['legal_profile'].pop('phone', None)

        response = patch_legal_profile(legal_profile_payload)

        legal_profile.refresh_from_db()
        legal_profile.identity_data.refresh_from_db()
        legal_profile.bank_data.refresh_from_db()
        legal_profile.company_data.refresh_from_db()

        assert response.status_code == status.HTTP_200_OK
        assert (
            response.data['legal_profile']['email']
            == (legal_profile_payload['legal_profile']['email'])
        )
        assert (
            legal_profile.email
            == (legal_profile_payload['legal_profile']['email'])
        )
        assert response.data['legal_profile']['phone'] == str(old_phone)
        assert legal_profile.phone == old_phone
        assert legal_profile.identity_data.first_name == old_first_name
        assert legal_profile.bank_data.bank_name == old_bank_name
        assert legal_profile.company_data.company_name == old_company_name

    def test_patch_resets_is_verified(
        self,
        artist_user,
        artist_legal_profile_factory,
        legal_profile_payload,
        patch_legal_profile,
    ):
        """Статус подтверждения сбрасывается при обновлении."""
        legal_profile = artist_legal_profile_factory(
            user=artist_user,
            is_verified=True,
        )

        response = patch_legal_profile(legal_profile_payload)
        legal_profile.refresh_from_db()

        assert response.status_code == status.HTTP_200_OK
        assert (
            legal_profile.email
            == (legal_profile_payload['legal_profile']['email'])
        )
        assert legal_profile.is_verified is False
        assert response.data['legal_profile']['is_verified'] is False

    def test_readonly_fields_do_not_change(
        self,
        artist_user,
        artist_legal_profile_factory,
        legal_profile_payload,
        patch_legal_profile,
    ):
        """Поля is_verified и comment не меняются артистом."""
        legal_profile = artist_legal_profile_factory(user=artist_user)
        old_is_verified = legal_profile.is_verified
        old_comment = legal_profile.comment

        legal_profile_payload['legal_profile']['is_verified'] = True
        legal_profile_payload['legal_profile']['comment'] = 'new comment'

        response = patch_legal_profile(legal_profile_payload)
        legal_profile.refresh_from_db()

        assert response.status_code == status.HTTP_200_OK
        assert response.data['legal_profile']['is_verified'] is old_is_verified
        assert legal_profile.is_verified is old_is_verified
        assert response.data['legal_profile']['comment'] == old_comment
        assert legal_profile.comment == old_comment
