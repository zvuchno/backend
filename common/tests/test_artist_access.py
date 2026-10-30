import pytest

from common.access import can_manage_artist


@pytest.mark.django_db
class TestCanManageArtist:
    """Права управления публичным профилем."""

    def test_active_superuser_can_manage_any_artist(
        self,
        artist_user,
        user_factory,
    ):
        """Активный суперпользователь управляет любым профилем."""
        superuser = user_factory(
            email='superuser@test.com',
            username='superuser',
            is_staff=True,
            is_superuser=True,
        )

        assert can_manage_artist(superuser, artist_user.artist_profile)

    def test_inactive_superuser_cannot_manage_foreign_artist(
        self,
        artist_user,
        user_factory,
    ):
        """Неактивный суперпользователь не получает обход проверки."""
        superuser = user_factory(
            email='inactive-superuser@test.com',
            username='inactive_superuser',
            is_active=False,
            is_staff=True,
            is_superuser=True,
        )

        assert not can_manage_artist(superuser, artist_user.artist_profile)

    def test_staff_cannot_manage_foreign_artist(
        self,
        artist_user,
        user_factory,
    ):
        """Обычный staff не получает полномочия суперпользователя."""
        staff = user_factory(
            email='ordinary-staff@test.com',
            username='ordinary_staff',
            is_staff=True,
            is_superuser=False,
        )

        assert not can_manage_artist(staff, artist_user.artist_profile)
