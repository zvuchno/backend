"""Тесты API управления паролем пользователя."""

import pytest
from rest_framework import status

from users.services import generate_password_reset_data
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


NEW_PASSWORD = 'FrostyPiano-482!'
ANOTHER_PASSWORD = 'VelvetRiver-937!'


class TestSetPasswordApi:
    """Тесты установки первого пароля."""

    def test_sets_password_for_user_without_usable_password(
        self,
        auth_client,
        user,
        account_set_password_url,
    ):
        """Пользователь без пароля может установить первый пароль."""
        user.set_unusable_password()
        user.save(update_fields=['password'])

        response = auth_client.post(
            account_set_password_url,
            data={
                'new_password': NEW_PASSWORD,
                'retype_new_password': NEW_PASSWORD,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            'detail': 'Пароль успешно установлен.',
        }

        user.refresh_from_db()
        assert user.has_usable_password()
        assert user.check_password(NEW_PASSWORD)

    def test_rejects_when_password_already_exists(
        self,
        auth_client,
        password_user,
        current_password,
        account_set_password_url,
    ):
        """Нельзя обойти смену пароля через set-password."""
        auth_client.force_authenticate(user=password_user)

        response = auth_client.post(
            account_set_password_url,
            data={
                'new_password': NEW_PASSWORD,
                'retype_new_password': NEW_PASSWORD,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            'detail': [
                'Пароль уже установлен. '
                'Для его изменения используйте change-password.',
            ],
        }

        password_user.refresh_from_db()
        assert password_user.check_password(current_password)

    def test_requires_authentication(
        self,
        api_client,
        account_set_password_url,
    ):
        """Анонимный пользователь не может установить пароль."""
        response = api_client.post(
            account_set_password_url,
            data={
                'new_password': NEW_PASSWORD,
                'retype_new_password': NEW_PASSWORD,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_rejects_mismatched_passwords(
        self,
        auth_client,
        user,
        account_set_password_url,
    ):
        """Новый пароль и подтверждение должны совпадать."""
        user.set_unusable_password()
        user.save(update_fields=['password'])

        response = auth_client.post(
            account_set_password_url,
            data={
                'new_password': NEW_PASSWORD,
                'retype_new_password': ANOTHER_PASSWORD,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            'retype_new_password': [
                'Новые пароли не совпадают.',
            ],
        }

        user.refresh_from_db()
        assert not user.has_usable_password()


class TestChangePasswordApi:
    """Тесты смены уже установленного пароля."""

    def test_changes_password(
        self,
        auth_client,
        password_user,
        current_password,
        change_password_url,
    ):
        """Пользователь меняет пароль при корректном старом пароле."""
        auth_client.force_authenticate(user=password_user)

        response = auth_client.post(
            change_password_url,
            data={
                'old_password': current_password,
                'new_password': NEW_PASSWORD,
                'retype_new_password': NEW_PASSWORD,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            'detail': 'Пароль успешно изменен.',
        }

        password_user.refresh_from_db()
        assert not password_user.check_password(current_password)
        assert password_user.check_password(NEW_PASSWORD)

    def test_rejects_incorrect_old_password(
        self,
        auth_client,
        password_user,
        change_password_url,
    ):
        """Нельзя сменить пароль без знания текущего."""
        auth_client.force_authenticate(user=password_user)

        response = auth_client.post(
            change_password_url,
            data={
                'old_password': 'WrongPassword-482!',
                'new_password': NEW_PASSWORD,
                'retype_new_password': NEW_PASSWORD,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            'old_password': [
                'Текущий пароль указан неверно.',
            ],
        }

    def test_rejects_mismatched_new_passwords(
        self,
        auth_client,
        password_user,
        current_password,
        change_password_url,
    ):
        """Новый пароль и подтверждение должны совпадать."""
        auth_client.force_authenticate(user=password_user)

        response = auth_client.post(
            change_password_url,
            data={
                'old_password': current_password,
                'new_password': NEW_PASSWORD,
                'retype_new_password': ANOTHER_PASSWORD,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            'retype_new_password': [
                'Новые пароли не совпадают.',
            ],
        }


class TestPasswordResetApi:
    """Тесты проверки и подтверждения сброса пароля."""

    def test_verifies_valid_reset_link(
        self,
        api_client,
        user,
        reset_password_verify_url,
    ):
        """Проверка принимает действующие uid и token."""
        reset_data = generate_password_reset_data(user)

        response = api_client.post(
            reset_password_verify_url,
            data=reset_data,
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            'detail': 'Ссылка действительна.',
        }

    def test_rejects_invalid_reset_token(
        self,
        api_client,
        user,
        reset_password_verify_url,
    ):
        """Проверка отклоняет недействительный token."""
        reset_data = generate_password_reset_data(user)
        reset_data['token'] = 'invalid-token'

        response = api_client.post(
            reset_password_verify_url,
            data=reset_data,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            'token': [
                'Ссылка недействительна.',
            ],
        }

    def test_resets_password_for_social_only_user(
        self,
        api_client,
        reset_password_confirm_url,
        reset_password_verify_url,
    ):
        """Сброс пароля работает для social-only пользователя."""
        user = UserFactory()
        user.set_unusable_password()
        user.save(update_fields=['password'])

        reset_data = generate_password_reset_data(user)

        response = api_client.post(
            reset_password_confirm_url,
            data={
                **reset_data,
                'new_password': NEW_PASSWORD,
                'retype_new_password': NEW_PASSWORD,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            'detail': 'Новый пароль сохранен.',
        }

        user.refresh_from_db()
        assert user.has_usable_password()
        assert user.check_password(NEW_PASSWORD)

        verify_response = api_client.post(
            reset_password_verify_url,
            data=reset_data,
            format='json',
        )

        assert verify_response.status_code == status.HTTP_400_BAD_REQUEST
        assert verify_response.data == {
            'token': [
                'Ссылка недействительна.',
            ],
        }

    def test_rejects_mismatched_new_passwords(
        self,
        api_client,
        password_user,
        current_password,
        reset_password_confirm_url,
    ):
        """Сброс не устанавливает пароль при несовпадении полей."""
        reset_data = generate_password_reset_data(password_user)

        response = api_client.post(
            reset_password_confirm_url,
            data={
                **reset_data,
                'new_password': NEW_PASSWORD,
                'retype_new_password': ANOTHER_PASSWORD,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            'retype_new_password': [
                'Пароли не совпадают.',
            ],
        }

        password_user.refresh_from_db()
        assert password_user.check_password(current_password)
