"""Тесты настроек магазина артиста или лейбла."""

from http import HTTPStatus

import pytest

from users.models import ArtistStoreSettings

pytestmark = pytest.mark.django_db


class TestArtistStoreSettingsAPI:
    """Тесты API настроек магазина."""

    def test_get_returns_null_when_settings_do_not_exist(
        self,
        artist_client,
        artist_me_store_settings_url,
    ):
        """При отсутствии настроек API возвращает null."""
        response = artist_client.get(artist_me_store_settings_url)

        assert response.status_code == HTTPStatus.OK
        assert response.data is None

    def test_put_creates_store_settings(
        self,
        artist_client,
        artist_user,
        artist_me_store_settings_url,
    ):
        """PUT создаёт настройки магазина собственного профиля."""
        response = artist_client.put(
            artist_me_store_settings_url,
            data={
                'support_email': 'support@example.com',
                'returns_email': 'returns@example.com',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        settings = ArtistStoreSettings.objects.get(
            artist=artist_user.artist_profile,
        )

        assert settings.support_email == 'support@example.com'
        assert settings.returns_email == 'returns@example.com'
        assert response.data == {
            'support_email': 'support@example.com',
            'returns_email': 'returns@example.com',
        }

    def test_repeated_put_updates_existing_store_settings(
        self,
        artist_client,
        artist_user,
        artist_me_store_settings_url,
    ):
        """Повторный PUT обновляет существующие настройки."""
        profile = artist_user.artist_profile
        settings = ArtistStoreSettings.objects.create(
            artist=profile,
            support_email='old-support@example.com',
            returns_email='old-returns@example.com',
        )

        response = artist_client.put(
            artist_me_store_settings_url,
            data={
                'support_email': 'new-support@example.com',
                'returns_email': 'new-returns@example.com',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK
        assert (
            ArtistStoreSettings.objects.filter(
                artist=profile,
            ).count()
            == 1
        )

        settings.refresh_from_db()

        assert settings.support_email == 'new-support@example.com'
        assert settings.returns_email == 'new-returns@example.com'

    def test_get_returns_own_store_settings(
        self,
        artist_client,
        artist_user,
        artist_me_store_settings_url,
    ):
        """GET возвращает собственные настройки профиля."""
        ArtistStoreSettings.objects.create(
            artist=artist_user.artist_profile,
            support_email='support@example.com',
            returns_email='returns@example.com',
        )

        response = artist_client.get(artist_me_store_settings_url)

        assert response.status_code == HTTPStatus.OK
        assert response.data == {
            'support_email': 'support@example.com',
            'returns_email': 'returns@example.com',
        }

    def test_put_allows_clearing_store_settings(
        self,
        artist_client,
        artist_user,
        artist_me_store_settings_url,
    ):
        """Пустые строки очищают настройки профиля."""
        settings = ArtistStoreSettings.objects.create(
            artist=artist_user.artist_profile,
            support_email='support@example.com',
            returns_email='returns@example.com',
        )

        response = artist_client.put(
            artist_me_store_settings_url,
            data={
                'support_email': '',
                'returns_email': '',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

        settings.refresh_from_db()

        assert settings.support_email == ''
        assert settings.returns_email == ''
        assert response.data == {
            'support_email': '',
            'returns_email': '',
        }

    @pytest.mark.parametrize(
        ('field_name', 'value'),
        (
            ('support_email', 'invalid-email'),
            ('returns_email', 'invalid-email'),
        ),
    )
    def test_put_rejects_invalid_email(
        self,
        artist_client,
        artist_me_store_settings_url,
        field_name,
        value,
    ):
        """API отклоняет некорректный email."""
        data = {
            'support_email': 'support@example.com',
            'returns_email': 'returns@example.com',
        }
        data[field_name] = value

        response = artist_client.put(
            artist_me_store_settings_url,
            data=data,
            format='json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert field_name in response.data
        assert not ArtistStoreSettings.objects.exists()

    def test_label_creates_managed_artist_store_settings(
        self,
        label_client,
        label_created_artist,
        managed_store_settings_url,
    ):
        """Лейбл создаёт настройки магазина управляемого артиста."""
        response = label_client.put(
            managed_store_settings_url(label_created_artist),
            data={
                'support_email': 'artist-support@example.com',
                'returns_email': 'artist-returns@example.com',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED
        assert ArtistStoreSettings.objects.filter(
            artist=label_created_artist,
            support_email='artist-support@example.com',
            returns_email='artist-returns@example.com',
        ).exists()

    def test_label_gets_managed_artist_store_settings(
        self,
        label_client,
        label_created_artist,
        managed_store_settings_url,
    ):
        """Лейбл получает настройки магазина управляемого артиста."""
        ArtistStoreSettings.objects.create(
            artist=label_created_artist,
            support_email='artist-support@example.com',
            returns_email='artist-returns@example.com',
        )

        response = label_client.get(
            managed_store_settings_url(label_created_artist),
        )

        assert response.status_code == HTTPStatus.OK
        assert response.data == {
            'support_email': 'artist-support@example.com',
            'returns_email': 'artist-returns@example.com',
        }

    def test_label_cannot_access_unmanaged_artist_store_settings(
        self,
        label_client,
        other_artist_user,
        managed_store_settings_url,
    ):
        """Лейбл не управляет настройками чужого артиста."""
        response = label_client.get(
            managed_store_settings_url(
                other_artist_user.artist_profile,
            ),
        )

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_artist_cannot_access_other_artist_store_settings(
        self,
        artist_client,
        other_artist_user,
        managed_store_settings_url,
    ):
        """Артист не управляет настройками другого артиста."""
        response = artist_client.get(
            managed_store_settings_url(
                other_artist_user.artist_profile,
            ),
        )

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_requires_authentication(
        self,
        api_client,
        artist_me_store_settings_url,
    ):
        """Неавторизованный пользователь не получает настройки."""
        response = api_client.get(artist_me_store_settings_url)

        assert response.status_code == HTTPStatus.UNAUTHORIZED


class TestArtistStoreSettingsFallback:
    """Тесты наследования настроек магазина от лейбла."""

    def test_artist_uses_own_support_email(
        self,
        label_created_artist,
    ):
        """Собственный email поддержки имеет приоритет."""
        label = label_created_artist.label

        ArtistStoreSettings.objects.create(
            artist=label,
            support_email='label-support@example.com',
        )
        ArtistStoreSettings.objects.create(
            artist=label_created_artist,
            support_email='artist-support@example.com',
        )

        assert (
            label_created_artist.effective_support_email
            == 'artist-support@example.com'
        )

    def test_artist_uses_label_support_email_when_own_is_missing(
        self,
        label_created_artist,
    ):
        """При отсутствии собственного email используется email лейбла."""
        ArtistStoreSettings.objects.create(
            artist=label_created_artist.label,
            support_email='label-support@example.com',
        )

        assert (
            label_created_artist.effective_support_email
            == 'label-support@example.com'
        )

    def test_artist_uses_label_support_email_when_own_is_empty(
        self,
        label_created_artist,
    ):
        """Пустой собственный email включает fallback на лейбл."""
        ArtistStoreSettings.objects.create(
            artist=label_created_artist.label,
            support_email='label-support@example.com',
        )
        ArtistStoreSettings.objects.create(
            artist=label_created_artist,
            support_email='',
        )

        assert (
            label_created_artist.effective_support_email
            == 'label-support@example.com'
        )

    def test_store_settings_fallback_is_applied_per_field(
        self,
        label_created_artist,
    ):
        """Настройки наследуются отдельно для каждого поля."""
        ArtistStoreSettings.objects.create(
            artist=label_created_artist.label,
            support_email='label-support@example.com',
            returns_email='label-returns@example.com',
        )
        ArtistStoreSettings.objects.create(
            artist=label_created_artist,
            support_email='artist-support@example.com',
            returns_email='',
        )

        assert (
            label_created_artist.effective_support_email
            == 'artist-support@example.com'
        )
        assert (
            label_created_artist.effective_returns_email
            == 'label-returns@example.com'
        )

    def test_profile_without_label_returns_empty_email(
        self,
        artist_user,
    ):
        """Без собственных настроек и лейбла возвращается пустая строка."""
        profile = artist_user.artist_profile

        assert profile.effective_support_email == ''
        assert profile.effective_returns_email == ''
