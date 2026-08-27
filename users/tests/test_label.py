from http import HTTPStatus

import pytest

from store.tests.factories import AlbumFactory, MerchFactory
from users.models import (
    ArtistProfile,
    ArtistProfileType,
    TokenInvitationStatus,
)
from users.services import ArtistMembershipService

pytestmark = pytest.mark.django_db


class TestLabelManagedProfileList:
    """Тесты списка профилей, доступных текущему лейблу."""

    def test_label_gets_self_and_managed_artists(
        self,
        label_client,
        label_user,
        label_created_artist,
        signed_artist_user,
        label_managed_profiles_url,
    ):
        response = label_client.get(label_managed_profiles_url)

        assert response.status_code == HTTPStatus.OK

        profiles = response.data

        assert [item['id'] for item in profiles] == [
            label_user.artist_profile.id,
            label_created_artist.id,
            signed_artist_user.artist_profile.id,
        ]

        label_data = profiles[0]
        created_artist_data = profiles[1]
        signed_artist_data = profiles[2]

        assert label_data['is_self'] is True
        assert label_data['profile_type'] == ArtistProfileType.LABEL
        assert label_data['has_account'] is True

        assert created_artist_data['is_self'] is False
        assert created_artist_data['has_account'] is False

        assert signed_artist_data['is_self'] is False
        assert signed_artist_data['has_account'] is True

    def test_returns_claim_invitation_resend_state(
        self,
        label_client,
        label_user,
        label_created_artist,
        artist_claim_factory,
        label_managed_profiles_url,
    ):
        """Возвращает состояние повторной отправки приглашения."""
        claim, _ = artist_claim_factory(
            artist=label_created_artist,
            label_user=label_user,
        )
        claim.invitation.register_send()

        response = label_client.get(label_managed_profiles_url)

        assert response.status_code == HTTPStatus.OK

        artist_data = next(
            item
            for item in response.data
            if item['id'] == label_created_artist.id
        )
        invitation_data = artist_data['claim_invitation']

        assert invitation_data['email'] == claim.invitation.recipient_email
        assert invitation_data['status'] == TokenInvitationStatus.PENDING
        assert invitation_data['can_resend'] is False
        assert invitation_data['resend_available_at'] is not None

    def test_excludes_foreign_and_inactive_profiles(
        self,
        label_client,
        label_user,
        artist_profile_factory,
        label_profile_factory,
        user_factory,
        label_managed_profiles_url,
    ):
        own_artist = artist_profile_factory(
            label=label_user.artist_profile,
            name='Own Artist',
        )
        artist_profile_factory(
            label=label_user.artist_profile,
            name='Inactive Artist',
            is_active=False,
        )

        foreign_label_user = user_factory(
            email='foreign-label@test.com',
            username='foreign_label',
        )
        foreign_label = label_profile_factory(
            user=foreign_label_user,
            name='Foreign Label',
        )
        artist_profile_factory(
            label=foreign_label,
            name='Foreign Artist',
        )

        response = label_client.get(label_managed_profiles_url)

        assert response.status_code == HTTPStatus.OK

        profiles = response.data

        assert len(profiles) == 2
        assert {item['id'] for item in profiles} == {
            label_user.artist_profile.id,
            own_artist.id,
        }

    def test_forbidden_for_artist(
        self,
        artist_client,
        label_managed_profiles_url,
    ):
        response = artist_client.get(label_managed_profiles_url)

        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_forbidden_for_listener(
        self,
        listener_client,
        label_managed_profiles_url,
    ):
        response = listener_client.get(label_managed_profiles_url)

        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_requires_authentication(
        self,
        api_client,
        label_managed_profiles_url,
    ):
        response = api_client.get(label_managed_profiles_url)

        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_label_creates_managed_artist(
        self,
        label_client,
        label_user,
        label_managed_profiles_url,
    ):
        payload = {
            'name': 'Новый артист',
            'description': 'Описание нового артиста.',
            'city': 'Курган',
        }

        response = label_client.post(
            label_managed_profiles_url,
            data=payload,
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        artist = ArtistProfile.objects.get(pk=response.data['id'])

        assert artist.name == payload['name']
        assert artist.description == payload['description']
        assert artist.city == payload['city']
        assert artist.profile_type == ArtistProfileType.ARTIST
        assert artist.label == label_user.artist_profile
        assert artist.user is None
        assert artist.is_active is True
        assert artist.slug
        assert response.data == {
            'id': artist.id,
            'name': payload['name'],
            'description': payload['description'],
            'city': payload['city'],
            'slug': artist.slug,
        }

    def test_label_cannot_create_managed_artist_with_existing_slug(
        self,
        label_user,
        label_client,
        artist_profile_factory,
        label_managed_profiles_url,
    ):
        artist_profile_factory(
            label=label_user.artist_profile,
            user=None,
            slug='existing-slug',
        )

        response = label_client.post(
            label_managed_profiles_url,
            data={
                'name': 'Новый артист',
                'slug': 'existing-slug',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert 'slug' in response.data

    def test_label_cannot_override_managed_artist_system_fields(
        self,
        label_client,
        label_user,
        label_managed_profiles_url,
    ):
        response = label_client.post(
            label_managed_profiles_url,
            data={
                'name': 'Новый артист',
                'profile_type': ArtistProfileType.LABEL,
                'label': 999999,
                'user': label_user.id,
                'is_active': False,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        artist = ArtistProfile.objects.get(pk=response.data['id'])

        assert artist.profile_type == ArtistProfileType.ARTIST
        assert artist.label == label_user.artist_profile
        assert artist.user is None
        assert artist.is_active is True

    def test_artist_cannot_create_managed_profile(
        self,
        artist_client,
        label_managed_profiles_url,
    ):
        response = artist_client.post(
            label_managed_profiles_url,
            data={'name': 'Новый артист'},
            format='json',
        )

        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_label_creates_managed_artist_with_name_only(
        self,
        label_client,
        label_user,
        label_managed_profiles_url,
    ):
        response = label_client.post(
            label_managed_profiles_url,
            data={'name': 'Новый артист'},
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        artist = ArtistProfile.objects.get(pk=response.data['id'])

        assert artist.name == 'Новый артист'
        assert artist.label == label_user.artist_profile

    def test_label_updates_managed_artist_slug(
        self,
        label_client,
        label_user,
        label_created_artist,
        managed_profile_detail_url,
    ):
        label_slug = label_user.artist_profile.slug

        response = label_client.patch(
            managed_profile_detail_url(label_created_artist),
            data={'slug': 'managed-artist-address'},
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

        label_created_artist.refresh_from_db()
        label_user.artist_profile.refresh_from_db()

        assert label_created_artist.slug == 'managed-artist-address'
        assert response.data['slug'] == 'managed-artist-address'
        assert label_user.artist_profile.slug == label_slug

    def test_label_cannot_update_foreign_artist(
        self,
        label_client,
        other_artist_user,
        managed_profile_detail_url,
    ):
        original_slug = other_artist_user.artist_profile.slug

        response = label_client.patch(
            managed_profile_detail_url(other_artist_user.artist_profile),
            data={'slug': 'stolen-address'},
            format='json',
        )

        assert response.status_code == HTTPStatus.NOT_FOUND

        other_artist_user.artist_profile.refresh_from_db()
        assert other_artist_user.artist_profile.slug == original_slug


@pytest.mark.django_db
class TestArtistLeaveLabel:
    """Тесты самостоятельного выхода артиста из лейбла."""

    def test_artist_leaves_label(
        self,
        signed_artist_user,
        client_factory,
        artist_legal_profile_factory,
        artist_leave_label_url,
    ):
        signed_artist_user.is_email_verified = True
        signed_artist_user.save(update_fields=('is_email_verified',))

        artist_legal_profile_factory(
            user=signed_artist_user,
            is_verified=True,
        )

        artist = signed_artist_user.artist_profile
        client = client_factory(signed_artist_user)

        response = client.post(artist_leave_label_url)

        assert response.status_code == HTTPStatus.NO_CONTENT

        artist.refresh_from_db()

        assert artist.label is None

    def test_artist_becomes_payout_recipient_after_leaving_label(
        self,
        signed_artist_user,
        client_factory,
        artist_legal_profile_factory,
        artist_leave_label_url,
    ):
        signed_artist_user.is_email_verified = True
        signed_artist_user.save(update_fields=('is_email_verified',))

        artist_legal_profile_factory(
            user=signed_artist_user,
            is_verified=True,
        )

        artist = signed_artist_user.artist_profile
        label = artist.label

        album = AlbumFactory(
            artist=artist,
            payout_recipient=label.user,
        )
        merch = MerchFactory(
            artist=artist,
            payout_recipient=label.user,
        )

        client = client_factory(signed_artist_user)

        response = client.post(artist_leave_label_url)

        assert response.status_code == HTTPStatus.NO_CONTENT

        artist.refresh_from_db()
        album.refresh_from_db()
        merch.refresh_from_db()

        assert artist.label is None
        assert album.payout_recipient == signed_artist_user
        assert merch.payout_recipient == signed_artist_user

    def test_leave_label_does_not_change_other_artist_content(
        self,
        signed_artist_user,
        client_factory,
        artist_profile_factory,
        artist_legal_profile_factory,
        artist_leave_label_url,
    ):
        signed_artist_user.is_email_verified = True
        signed_artist_user.save(update_fields=('is_email_verified',))

        artist_legal_profile_factory(
            user=signed_artist_user,
            is_verified=True,
        )

        artist = signed_artist_user.artist_profile
        label = artist.label

        another_artist = artist_profile_factory(
            label=label,
        )

        album = AlbumFactory(
            artist=another_artist,
            payout_recipient=label.user,
        )
        merch = MerchFactory(
            artist=another_artist,
            payout_recipient=label.user,
        )

        client = client_factory(signed_artist_user)

        response = client.post(artist_leave_label_url)

        assert response.status_code == HTTPStatus.NO_CONTENT

        album.refresh_from_db()
        merch.refresh_from_db()

        assert album.payout_recipient == label.user
        assert merch.payout_recipient == label.user

    def test_unverified_artist_email_cannot_leave_label(
        self,
        signed_artist_user,
        client_factory,
        artist_legal_profile_factory,
        artist_leave_label_url,
    ):
        signed_artist_user.is_email_verified = False
        signed_artist_user.save(update_fields=('is_email_verified',))

        artist_legal_profile_factory(
            user=signed_artist_user,
            is_verified=True,
        )

        artist = signed_artist_user.artist_profile
        label = artist.label

        client = client_factory(signed_artist_user)

        response = client.post(artist_leave_label_url)

        assert response.status_code == HTTPStatus.BAD_REQUEST

        artist.refresh_from_db()

        assert artist.label == label

    def test_artist_without_legal_profile_cannot_leave_label(
        self,
        signed_artist_user,
        client_factory,
        artist_leave_label_url,
    ):
        signed_artist_user.is_email_verified = True
        signed_artist_user.save(update_fields=('is_email_verified',))

        artist = signed_artist_user.artist_profile
        label = artist.label

        client = client_factory(signed_artist_user)

        response = client.post(artist_leave_label_url)

        assert response.status_code == HTTPStatus.BAD_REQUEST

        artist.refresh_from_db()

        assert artist.label == label

    def test_artist_with_unverified_legal_profile_cannot_leave_label(
        self,
        signed_artist_user,
        client_factory,
        artist_legal_profile_factory,
        artist_leave_label_url,
    ):
        signed_artist_user.is_email_verified = True
        signed_artist_user.save(update_fields=('is_email_verified',))

        artist_legal_profile_factory(
            user=signed_artist_user,
            is_verified=False,
        )

        artist = signed_artist_user.artist_profile
        label = artist.label

        client = client_factory(signed_artist_user)

        response = client.post(artist_leave_label_url)

        assert response.status_code == HTTPStatus.BAD_REQUEST

        artist.refresh_from_db()

        assert artist.label == label

    def test_artist_without_label_cannot_leave(
        self,
        artist_user,
        client_factory,
        artist_legal_profile_factory,
        artist_leave_label_url,
    ):
        artist_user.is_email_verified = True
        artist_user.save(update_fields=('is_email_verified',))

        artist_legal_profile_factory(
            user=artist_user,
            is_verified=True,
        )

        artist = artist_user.artist_profile
        client = client_factory(artist_user)

        response = client.post(artist_leave_label_url)

        assert response.status_code == HTTPStatus.BAD_REQUEST

        artist.refresh_from_db()

        assert artist.label is None

    def test_label_cannot_leave_label(
        self,
        label_user,
        client_factory,
        artist_leave_label_url,
    ):
        client = client_factory(label_user)

        response = client.post(artist_leave_label_url)

        assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.django_db
class TestArtistMembershipPayoutRecipient:
    """Тесты состояния получателя выплат."""

    def test_sync_payout_recipient_updates_artist_content(
        self,
        artist_user,
        label_user,
    ):
        """Синхронизация передаёт выплаты за контент текущему лейблу."""
        artist = artist_user.artist_profile
        label = label_user.artist_profile

        album = AlbumFactory(
            artist=artist,
        )
        merch = MerchFactory(
            artist=artist,
        )

        assert album.payout_recipient == artist_user
        assert merch.payout_recipient == artist_user

        artist.label = label
        artist.save(update_fields=('label',))

        ArtistMembershipService.sync_payout_recipient(
            artist=artist,
        )

        album.refresh_from_db()
        merch.refresh_from_db()

        assert album.payout_recipient == label_user
        assert merch.payout_recipient == label_user

    def test_sync_payout_recipient_updates_content_after_label_change(
        self,
        artist_user,
        label_user,
        user_factory,
        label_profile_factory,
    ):
        """При смене лейбла выплаты передаются новому лейблу."""
        artist = artist_user.artist_profile
        first_label = label_user.artist_profile

        second_label_user = user_factory(
            email='second-label@test.com',
            username='second_label',
        )
        second_label = label_profile_factory(
            user=second_label_user,
            name='Second Label',
        )

        artist.label = first_label
        artist.save(update_fields=('label',))

        album = AlbumFactory(
            artist=artist,
        )

        assert album.payout_recipient == label_user

        artist.label = second_label
        artist.save(update_fields=('label',))

        ArtistMembershipService.sync_payout_recipient(
            artist=artist,
        )

        album.refresh_from_db()

        assert album.payout_recipient == second_label_user
