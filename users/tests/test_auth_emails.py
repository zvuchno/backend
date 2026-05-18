import re

import pytest
from django.core import mail
from rest_framework import status

pytestmark = pytest.mark.django_db


class TestAuthEmails:
    """Тесты отправки писем в auth flow."""

    UID_PATTERN = r'uid=[^&"\s]+'
    TOKEN_PATTERN = r'token=[^&"\s]+'

    def test_listener_registration_sends_verification_email(
        self,
        api_client,
        listener_register_payload,
        listener_register_url,
    ):
        """Письмо после регистрации слушателя."""
        response = api_client.post(
            listener_register_url,
            data=listener_register_payload,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        assert len(mail.outbox) == 1

        message = mail.outbox[0]
        assert isinstance(message, mail.EmailMultiAlternatives)
        assert message.to == [listener_register_payload['email']]
        assert 'Подтверждение email'.lower() in message.subject.lower()

        assert re.search(self.UID_PATTERN, str(message.body))
        assert re.search(self.TOKEN_PATTERN, str(message.body))

        assert len(message.alternatives) == 1

        html_body, mime_type = message.alternatives[0]

        assert mime_type == 'text/html'
        assert re.search(self.UID_PATTERN, str(html_body))
        assert re.search(self.TOKEN_PATTERN, str(html_body))

    def test_artist_registration_sends_verification_email(
        self,
        api_client,
        artist_register_payload,
        artist_register_url,
    ):
        """Письмо после регистрации артиста."""
        response = api_client.post(
            artist_register_url,
            data=artist_register_payload,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        assert len(mail.outbox) == 1

        message = mail.outbox[0]
        assert isinstance(message, mail.EmailMultiAlternatives)
        assert message.to == [artist_register_payload['email']]
        assert 'Подтверждение email'.lower() in message.subject.lower()

        assert re.search(self.UID_PATTERN, str(message.body))
        assert re.search(self.TOKEN_PATTERN, str(message.body))

        assert len(message.alternatives) == 1

        html_body, mime_type = message.alternatives[0]

        assert mime_type == 'text/html'
        assert re.search(self.UID_PATTERN, str(html_body))
        assert re.search(self.TOKEN_PATTERN, str(html_body))

    def test_resend_verification_email_sends_email(
        self,
        user,
        auth_client,
        resend_email_verification_url,
    ):
        """Повторное письмо подтверждения почты."""
        response = auth_client.post(resend_email_verification_url)

        assert response.status_code == status.HTTP_200_OK

        assert len(mail.outbox) == 1

        message = mail.outbox[0]
        assert isinstance(message, mail.EmailMultiAlternatives)
        assert message.to == [user.email]
        assert 'Подтверждение email'.lower() in message.subject.lower()

        assert re.search(self.UID_PATTERN, str(message.body))
        assert re.search(self.TOKEN_PATTERN, str(message.body))

        assert len(message.alternatives) == 1

        html_body, mime_type = message.alternatives[0]

        assert mime_type == 'text/html'
        assert re.search(self.UID_PATTERN, str(html_body))
        assert re.search(self.TOKEN_PATTERN, str(html_body))

    def test_password_reset_sends_email_for_existing_user(
        self,
        user,
        api_client,
        reset_password_url,
    ):
        """Письмо сброса пароля для существующего email."""
        response = api_client.post(
            reset_password_url,
            data={'email': user.email},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK

        assert len(mail.outbox) == 1

        message = mail.outbox[0]
        assert isinstance(message, mail.EmailMultiAlternatives)
        assert message.to == [user.email]
        assert 'Восстановление пароля'.lower() in message.subject.lower()

        assert re.search(self.UID_PATTERN, str(message.body))
        assert re.search(self.TOKEN_PATTERN, str(message.body))

        assert len(message.alternatives) == 1

        html_body, mime_type = message.alternatives[0]

        assert mime_type == 'text/html'
        assert re.search(self.UID_PATTERN, str(html_body))
        assert re.search(self.TOKEN_PATTERN, str(html_body))

    def test_password_reset_does_not_send_email_for_unknown_user(
        self,
        api_client,
        reset_password_url,
    ):
        """Письмо сброса пароля не уходит на неизвестный email."""
        response = api_client.post(
            reset_password_url,
            data={'email': 'non@existing.email'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(mail.outbox) == 0
