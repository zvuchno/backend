"""Тесты приглашений на управление профилем артиста."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import status

from config import settings
from users.models import (
    ArtistProfileClaimInvitation,
    TokenInvitation,
    TokenInvitationStatus,
)
from users.tasks.invitation import expire_token_invitations
from users.tests.factories import (
    ArtistProfileFactory,
    ArtistUserFactory,
    LabelUserFactory,
    ListenerUserFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


class TestArtistProfileClaimInvitationCreate:
    """Тесты создания приглашения лейблом."""

    @patch(
        'users.services.invitation.send_artist_profile_claim_invitation_mail',
    )
    def test_label_creates_invitation(
        self,
        mock_send_mail,
        auth_client,
        managed_artist_claim_create_url,
        django_capture_on_commit_callbacks,
    ):
        label_user = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        auth_client.force_authenticate(user=label_user)

        with django_capture_on_commit_callbacks(execute=True):
            response = auth_client.post(
                managed_artist_claim_create_url(artist),
                {
                    'email': 'invited@test.local',
                },
                format='json',
            )

        assert response.status_code == status.HTTP_201_CREATED

        claim = ArtistProfileClaimInvitation.objects.get(
            artist=artist,
        )
        invitation = claim.invitation

        assert invitation.recipient_email == 'invited@test.local'
        assert invitation.status == TokenInvitationStatus.PENDING
        assert invitation.created_by == label_user
        assert invitation.token_hash
        assert invitation.expires_at > timezone.now()
        assert invitation.send_count == 1
        assert invitation.last_sent_at is not None
        assert invitation.can_resend is False
        assert invitation.resend_available_at > timezone.now()

        mock_send_mail.assert_called_once()

    def test_artist_cannot_create_invitation(
        self,
        auth_client,
        managed_artist_claim_create_url,
    ):
        label_user = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        artist_user = ArtistUserFactory()
        auth_client.force_authenticate(user=artist_user)

        response = auth_client.post(
            managed_artist_claim_create_url(artist),
            {
                'email': 'invited@test.local',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert ArtistProfileClaimInvitation.objects.count() == 0

    def test_label_cannot_invite_artist_of_another_label(
        self,
        auth_client,
        managed_artist_claim_create_url,
    ):
        owner_label = LabelUserFactory()
        another_label = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=owner_label.artist_profile,
        )
        auth_client.force_authenticate(user=another_label)

        response = auth_client.post(
            managed_artist_claim_create_url(artist),
            {
                'email': 'invited@test.local',
            },
            format='json',
        )

        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )
        assert ArtistProfileClaimInvitation.objects.count() == 0

    def test_cannot_invite_artist_with_account(
        self,
        auth_client,
        managed_artist_claim_create_url,
    ):
        label_user = LabelUserFactory()
        artist_user = UserFactory()
        artist = ArtistProfileFactory(
            user=artist_user,
            label=label_user.artist_profile,
        )
        auth_client.force_authenticate(user=label_user)

        response = auth_client.post(
            managed_artist_claim_create_url(artist),
            {
                'email': 'invited@test.local',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert ArtistProfileClaimInvitation.objects.count() == 0

    def test_cannot_invite_registered_email(
        self,
        auth_client,
        managed_artist_claim_create_url,
    ):
        label_user = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        existing_user = UserFactory()
        auth_client.force_authenticate(user=label_user)

        response = auth_client.post(
            managed_artist_claim_create_url(artist),
            {
                'email': existing_user.email,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert ArtistProfileClaimInvitation.objects.count() == 0

    def test_cannot_create_second_invitation(
        self,
        auth_client,
        artist_claim_factory,
        managed_artist_claim_create_url,
    ):
        label_user = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        artist_claim_factory(
            artist=artist,
            label_user=label_user,
        )
        auth_client.force_authenticate(user=label_user)

        response = auth_client.post(
            managed_artist_claim_create_url(artist),
            {
                'email': 'another@test.local',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            ArtistProfileClaimInvitation.objects.filter(
                artist=artist,
            ).count()
            == 1
        )

    def test_database_prevents_second_claim_for_artist(
        self,
        artist_claim_factory,
    ):
        """База запрещает второе приглашение для одного профиля."""
        claim, _ = artist_claim_factory()

        another_invitation = TokenInvitation.objects.create(
            recipient_email='another@test.local',
            token_hash='another-token-hash',
            created_by=claim.invitation.created_by,
            expires_at=timezone.now() + timedelta(days=1),
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ArtistProfileClaimInvitation.objects.create(
                    artist=claim.artist,
                    invitation=another_invitation,
                )

    @pytest.mark.parametrize(
        ('template_name', 'context'),
        [
            (
                'artist_profile_claim_invitation',
                {
                    'artist_name': 'Артист',
                    'label_name': 'Лейбл',
                    'invitation_url': 'https://example.com/invite',
                },
            ),
            (
                'artist_profile_claim_accepted',
                {
                    'artist_name': 'Артист',
                    'recipient_email': 'artist@example.com',
                },
            ),
            (
                'artist_profile_claim_rejected',
                {
                    'artist_name': 'Артист',
                    'recipient_email': 'artist@example.com',
                },
            ),
        ],
    )
    def test_artist_claim_email_templates_render(
        self,
        template_name,
        context,
    ):
        """Проверяет рендер шаблонов писем приглашения."""
        html = render_to_string(
            f'emails/{template_name}.html',
            context,
        )
        text = render_to_string(
            f'emails/{template_name}.txt',
            context,
        )

        assert html
        assert text
        assert 'Артист' in html
        assert 'Артист' in text


class TestArtistProfileClaimInvitationRead:
    """Тесты просмотра приглашения получателем."""

    def test_reads_invitation_without_authentication(
        self,
        api_client,
        artist_claim_factory,
        artist_claim_read_url,
    ):
        claim, token = artist_claim_factory()

        response = api_client.get(
            artist_claim_read_url,
            {
                'token': token,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['artist_id'] == claim.artist_id
        assert response.data['artist_name'] == claim.artist.name
        assert response.data['label_id'] == claim.artist.label_id
        assert response.data['label_name'] == claim.artist.label.name
        assert response.data['status'] == TokenInvitationStatus.PENDING
        assert response.data['expires_at'] is not None

    def test_requires_token(
        self,
        api_client,
        artist_claim_read_url,
    ):
        response = api_client.get(artist_claim_read_url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'token' in response.data

    def test_invalid_token_returns_400(
        self,
        api_client,
        artist_claim_read_url,
    ):
        response = api_client.get(
            artist_claim_read_url,
            {
                'token': 'invalid-token',
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'token' in response.data

    @pytest.mark.parametrize(
        'invitation_status',
        [
            TokenInvitationStatus.REJECTED,
            TokenInvitationStatus.REVOKED,
            TokenInvitationStatus.EXPIRED,
            TokenInvitationStatus.ACCEPTED,
        ],
    )
    def test_returns_non_pending_invitation(
        self,
        invitation_status,
        api_client,
        artist_claim_factory,
        artist_claim_read_url,
    ):
        claim, token = artist_claim_factory(
            status=invitation_status,
        )

        response = api_client.get(
            artist_claim_read_url,
            {
                'token': token,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == invitation_status
        assert response.data['artist_id'] == claim.artist_id

    def test_read_marks_expired_invitation_as_expired(
        self,
        api_client,
        artist_claim_factory,
        artist_claim_read_url,
    ):
        claim, token = artist_claim_factory(
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        response = api_client.get(
            artist_claim_read_url,
            {
                'token': token,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == TokenInvitationStatus.EXPIRED

        claim.invitation.refresh_from_db()
        assert claim.invitation.status == TokenInvitationStatus.EXPIRED


class TestArtistProfileClaimInvitationAccept:
    """Тесты принятия приглашения."""

    @patch(
        'users.services.invitation.send_artist_profile_claim_accepted_mail',
    )
    def test_accept_assigns_artist_and_verifies_email(
        self,
        mock_send_mail,
        auth_client,
        artist_claim_factory,
        artist_claim_accept_url,
        django_capture_on_commit_callbacks,
    ):
        user = ListenerUserFactory(
            email='invited@test.local',
            is_email_verified=False,
        )
        claim, token = artist_claim_factory(
            email=user.email,
        )
        auth_client.force_authenticate(user=user)

        with django_capture_on_commit_callbacks(execute=True):
            response = auth_client.post(
                artist_claim_accept_url,
                {
                    'token': token,
                },
                format='json',
            )

        assert response.status_code == status.HTTP_200_OK

        claim.artist.refresh_from_db()
        claim.invitation.refresh_from_db()
        user.refresh_from_db()

        assert claim.artist.user == user
        assert user.is_email_verified is True
        assert claim.invitation.status == TokenInvitationStatus.ACCEPTED
        assert claim.invitation.responded_by == user
        assert claim.invitation.responded_at is not None

        mock_send_mail.assert_called_once()

    def test_requires_authentication(
        self,
        api_client,
        artist_claim_factory,
        artist_claim_accept_url,
    ):
        _, token = artist_claim_factory()

        response = api_client.post(
            artist_claim_accept_url,
            {
                'token': token,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_cannot_accept_with_another_email(
        self,
        auth_client,
        artist_claim_factory,
        artist_claim_accept_url,
    ):
        user = ListenerUserFactory(
            email='another@test.local',
            is_email_verified=False,
        )
        claim, token = artist_claim_factory(
            email='invited@test.local',
        )
        auth_client.force_authenticate(user=user)

        response = auth_client.post(
            artist_claim_accept_url,
            {
                'token': token,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        user.refresh_from_db()
        claim.artist.refresh_from_db()
        claim.invitation.refresh_from_db()

        assert user.is_email_verified is False
        assert claim.artist.user_id is None
        assert claim.invitation.status == TokenInvitationStatus.PENDING

    def test_cannot_accept_expired_invitation(
        self,
        auth_client,
        artist_claim_factory,
        artist_claim_accept_url,
    ):
        user = ListenerUserFactory(
            email='invited@test.local',
            is_email_verified=False,
        )
        claim, token = artist_claim_factory(
            email=user.email,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        auth_client.force_authenticate(user=user)

        response = auth_client.post(
            artist_claim_accept_url,
            {
                'token': token,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        user.refresh_from_db()
        claim.artist.refresh_from_db()

        assert user.is_email_verified is False
        assert claim.artist.user_id is None

    @pytest.mark.parametrize(
        'invitation_status',
        [
            TokenInvitationStatus.REJECTED,
            TokenInvitationStatus.REVOKED,
            TokenInvitationStatus.ACCEPTED,
            TokenInvitationStatus.EXPIRED,
        ],
    )
    def test_cannot_accept_non_pending_invitation(
        self,
        invitation_status,
        auth_client,
        artist_claim_factory,
        artist_claim_accept_url,
    ):
        user = ListenerUserFactory(
            email='invited@test.local',
            is_email_verified=False,
        )
        claim, token = artist_claim_factory(
            email=user.email,
            status=invitation_status,
        )
        auth_client.force_authenticate(user=user)

        response = auth_client.post(
            artist_claim_accept_url,
            {
                'token': token,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        user.refresh_from_db()
        claim.artist.refresh_from_db()

        assert user.is_email_verified is False
        assert claim.artist.user_id is None

    def test_cannot_accept_when_artist_already_has_account(
        self,
        auth_client,
        artist_claim_factory,
        artist_claim_accept_url,
    ):
        user = ListenerUserFactory(
            email='invited@test.local',
            is_email_verified=False,
        )
        claim, token = artist_claim_factory(
            email=user.email,
        )
        claim.artist.user = UserFactory()
        claim.artist.save(update_fields=('user',))

        auth_client.force_authenticate(user=user)

        response = auth_client.post(
            artist_claim_accept_url,
            {
                'token': token,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        user.refresh_from_db()
        assert user.is_email_verified is False

    def test_user_with_artist_profile_cannot_accept(
        self,
        auth_client,
        artist_claim_factory,
        artist_claim_accept_url,
    ):
        user = ArtistUserFactory(
            email='invited@test.local',
            is_email_verified=False,
        )
        claim, token = artist_claim_factory(
            email=user.email,
        )
        auth_client.force_authenticate(user=user)

        response = auth_client.post(
            artist_claim_accept_url,
            {
                'token': token,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        claim.artist.refresh_from_db()
        user.refresh_from_db()

        assert claim.artist.user_id is None
        assert user.is_email_verified is False

    def test_invalid_token_returns_400(
        self,
        auth_client,
        artist_claim_accept_url,
    ):
        user = ListenerUserFactory(
            is_email_verified=False,
        )
        auth_client.force_authenticate(user=user)

        response = auth_client.post(
            artist_claim_accept_url,
            {
                'token': 'invalid-token',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        user.refresh_from_db()
        assert user.is_email_verified is False


class TestArtistProfileClaimInvitationReject:
    """Тесты отклонения приглашения."""

    @patch(
        'users.services.invitation.send_artist_profile_claim_rejected_mail',
    )
    def test_reject_without_authentication(
        self,
        mock_send_mail,
        api_client,
        artist_claim_factory,
        artist_claim_reject_url,
        django_capture_on_commit_callbacks,
    ):
        claim, token = artist_claim_factory()

        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                artist_claim_reject_url,
                {
                    'token': token,
                },
                format='json',
            )

        assert response.status_code == status.HTTP_200_OK

        claim.invitation.refresh_from_db()

        assert claim.invitation.status == TokenInvitationStatus.REJECTED
        assert claim.invitation.responded_by is None
        assert claim.invitation.responded_at is not None

        mock_send_mail.assert_called_once()

    def test_invalid_token_returns_400(
        self,
        api_client,
        artist_claim_reject_url,
    ):
        response = api_client.post(
            artist_claim_reject_url,
            {
                'token': 'invalid-token',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_reject_expired_invitation(
        self,
        api_client,
        artist_claim_factory,
        artist_claim_reject_url,
    ):
        claim, token = artist_claim_factory(
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        response = api_client.post(
            artist_claim_reject_url,
            {
                'token': token,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        claim.invitation.refresh_from_db()
        assert claim.invitation.status == TokenInvitationStatus.PENDING

    @pytest.mark.parametrize(
        'invitation_status',
        [
            TokenInvitationStatus.REJECTED,
            TokenInvitationStatus.REVOKED,
            TokenInvitationStatus.ACCEPTED,
            TokenInvitationStatus.EXPIRED,
        ],
    )
    def test_cannot_reject_non_pending_invitation(
        self,
        invitation_status,
        api_client,
        artist_claim_factory,
        artist_claim_reject_url,
    ):
        claim, token = artist_claim_factory(
            status=invitation_status,
        )

        response = api_client.post(
            artist_claim_reject_url,
            {
                'token': token,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        claim.invitation.refresh_from_db()
        assert claim.invitation.status == invitation_status


class TestArtistProfileClaimInvitationResend:
    """Тесты повторной отправки приглашения."""

    @patch(
        'users.services.invitation.send_artist_profile_claim_invitation_mail',
    )
    def test_label_resends_invitation(
        self,
        mock_send_mail,
        auth_client,
        artist_claim_factory,
        managed_artist_claim_resend_url,
        django_capture_on_commit_callbacks,
    ):
        label_user = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        claim, _ = artist_claim_factory(
            artist=artist,
            label_user=label_user,
            status=TokenInvitationStatus.REJECTED,
        )

        old_hash = claim.invitation.token_hash
        old_expires_at = claim.invitation.expires_at

        auth_client.force_authenticate(user=label_user)

        with django_capture_on_commit_callbacks(execute=True):
            response = auth_client.post(
                managed_artist_claim_resend_url(artist),
                format='json',
            )

        assert response.status_code == status.HTTP_200_OK

        claim.invitation.refresh_from_db()

        assert claim.invitation.token_hash != old_hash
        assert claim.invitation.expires_at > old_expires_at
        assert claim.invitation.status == TokenInvitationStatus.PENDING
        assert claim.invitation.responded_by is None
        assert claim.invitation.responded_at is None

        mock_send_mail.assert_called_once()

    def test_cannot_resend_during_cooldown(
        self,
        auth_client,
        artist_claim_factory,
        managed_artist_claim_resend_url,
    ):
        """Нельзя повторно отправить приглашение во время кулдауна."""
        label_user = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        claim, _ = artist_claim_factory(
            artist=artist,
            label_user=label_user,
        )
        claim.invitation.register_send()

        auth_client.force_authenticate(user=label_user)

        response = auth_client.post(
            managed_artist_claim_resend_url(artist),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        claim.invitation.refresh_from_db()

        assert claim.invitation.send_count == 1
        assert claim.invitation.status == TokenInvitationStatus.PENDING

    def test_can_resend_after_cooldown(
        self,
        auth_client,
        artist_claim_factory,
        managed_artist_claim_resend_url,
    ):
        """После окончания кулдауна приглашение можно отправить повторно."""
        label_user = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        claim, _ = artist_claim_factory(
            artist=artist,
            label_user=label_user,
        )

        claim.invitation.send_count = 1
        claim.invitation.last_sent_at = timezone.now() - timedelta(
            seconds=settings.INVITATION_RESEND_COOLDOWN_SECONDS + 1,
        )
        claim.invitation.save(
            update_fields=(
                'send_count',
                'last_sent_at',
                'updated_at',
            ),
        )

        auth_client.force_authenticate(user=label_user)

        response = auth_client.post(
            managed_artist_claim_resend_url(artist),
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK

        claim.invitation.refresh_from_db()

        assert claim.invitation.send_count == 2
        assert claim.invitation.last_sent_at > (
            timezone.now() - timedelta(seconds=5)
        )
        assert claim.invitation.can_resend is False

    def test_resend_changes_recipient_email(
        self,
        auth_client,
        artist_claim_factory,
        managed_artist_claim_resend_url,
    ):
        """При повторной отправке можно изменить email получателя."""
        label_user = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        claim, _ = artist_claim_factory(
            artist=artist,
            label_user=label_user,
            email='wrong@test.local',
        )

        old_hash = claim.invitation.token_hash

        auth_client.force_authenticate(user=label_user)

        response = auth_client.post(
            managed_artist_claim_resend_url(artist),
            {
                'email': 'correct@test.local',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK

        claim.invitation.refresh_from_db()

        assert claim.invitation.recipient_email == 'correct@test.local'
        assert claim.invitation.token_hash != old_hash
        assert response.data['email'] == 'correct@test.local'

    def test_cannot_change_recipient_to_registered_email(
        self,
        auth_client,
        artist_claim_factory,
        managed_artist_claim_resend_url,
    ):
        """Нельзя сменить на email существующего пользователя."""
        label_user = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        claim, _ = artist_claim_factory(
            artist=artist,
            label_user=label_user,
            email='old@test.local',
        )
        existing_user = UserFactory()

        old_hash = claim.invitation.token_hash

        auth_client.force_authenticate(user=label_user)

        response = auth_client.post(
            managed_artist_claim_resend_url(artist),
            {
                'email': existing_user.email,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        claim.invitation.refresh_from_db()

        assert claim.invitation.recipient_email == 'old@test.local'
        assert claim.invitation.token_hash == old_hash

    def test_resend_invalidates_old_token(
        self,
        auth_client,
        api_client,
        artist_claim_factory,
        managed_artist_claim_resend_url,
        artist_claim_read_url,
    ):
        label_user = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        _, old_token = artist_claim_factory(
            artist=artist,
            label_user=label_user,
        )

        auth_client.force_authenticate(user=label_user)

        response = auth_client.post(
            managed_artist_claim_resend_url(artist),
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK

        response = api_client.get(
            artist_claim_read_url,
            {
                'token': old_token,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_resend_accepted_invitation(
        self,
        auth_client,
        artist_claim_factory,
        managed_artist_claim_resend_url,
    ):
        label_user = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        artist_claim_factory(
            artist=artist,
            label_user=label_user,
            status=TokenInvitationStatus.ACCEPTED,
        )

        auth_client.force_authenticate(user=label_user)

        response = auth_client.post(
            managed_artist_claim_resend_url(artist),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_another_label_cannot_resend_invitation(
        self,
        auth_client,
        artist_claim_factory,
        managed_artist_claim_resend_url,
    ):
        owner_label = LabelUserFactory()
        another_label = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=owner_label.artist_profile,
        )
        artist_claim_factory(
            artist=artist,
            label_user=owner_label,
        )

        auth_client.force_authenticate(user=another_label)

        response = auth_client.post(
            managed_artist_claim_resend_url(artist),
            format='json',
        )

        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )


class TestArtistProfileClaimInvitationRevoke:
    """Тесты отзыва приглашения."""

    def test_label_revokes_pending_invitation(
        self,
        auth_client,
        artist_claim_factory,
        managed_artist_claim_revoke_url,
    ):
        label_user = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        claim, _ = artist_claim_factory(
            artist=artist,
            label_user=label_user,
        )

        auth_client.force_authenticate(user=label_user)

        response = auth_client.post(
            managed_artist_claim_revoke_url(artist),
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK

        claim.invitation.refresh_from_db()

        assert claim.invitation.status == TokenInvitationStatus.REVOKED
        assert response.data['status'] == TokenInvitationStatus.REVOKED

    @pytest.mark.parametrize(
        'invitation_status',
        [
            TokenInvitationStatus.REJECTED,
            TokenInvitationStatus.EXPIRED,
            TokenInvitationStatus.ACCEPTED,
            TokenInvitationStatus.REVOKED,
        ],
    )
    def test_cannot_revoke_non_pending_invitation(
        self,
        invitation_status,
        auth_client,
        artist_claim_factory,
        managed_artist_claim_revoke_url,
    ):
        label_user = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        claim, _ = artist_claim_factory(
            artist=artist,
            label_user=label_user,
            status=invitation_status,
        )

        auth_client.force_authenticate(user=label_user)

        response = auth_client.post(
            managed_artist_claim_revoke_url(artist),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        claim.invitation.refresh_from_db()
        assert claim.invitation.status == invitation_status

    def test_another_label_cannot_revoke_invitation(
        self,
        auth_client,
        artist_claim_factory,
        managed_artist_claim_revoke_url,
    ):
        owner_label = LabelUserFactory()
        another_label = LabelUserFactory()
        artist = ArtistProfileFactory(
            user=None,
            label=owner_label.artist_profile,
        )
        artist_claim_factory(
            artist=artist,
            label_user=owner_label,
        )

        auth_client.force_authenticate(user=another_label)

        response = auth_client.post(
            managed_artist_claim_revoke_url(artist),
            format='json',
        )

        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )


class TestExpireTokenInvitations:
    """Тесты истечения срока действия приглашений."""

    def test_marks_expired_pending_invitation_as_expired(
        self,
        artist_claim_factory,
    ):
        claim, _ = artist_claim_factory(
            token='expired-token',
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        updated = expire_token_invitations()

        claim.invitation.refresh_from_db()

        assert updated == 1
        assert claim.invitation.status == TokenInvitationStatus.EXPIRED

    def test_does_not_expire_active_invitation(
        self,
        artist_claim_factory,
    ):
        claim, _ = artist_claim_factory(
            token='active-token',
            expires_at=timezone.now() + timedelta(days=1),
        )

        updated = expire_token_invitations()

        claim.invitation.refresh_from_db()

        assert updated == 0
        assert claim.invitation.status == TokenInvitationStatus.PENDING

    def test_does_not_change_non_pending_invitation(
        self,
        artist_claim_factory,
    ):
        claim, _ = artist_claim_factory(
            token='rejected-token',
            status=TokenInvitationStatus.REJECTED,
            expires_at=timezone.now() - timedelta(days=1),
        )

        updated = expire_token_invitations()

        claim.invitation.refresh_from_db()

        assert updated == 0
        assert claim.invitation.status == TokenInvitationStatus.REJECTED
