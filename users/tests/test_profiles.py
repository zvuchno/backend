"""Тесты API профилей артистов и лейблов."""

from http import HTTPStatus

import pytest
from django.core.cache import cache
from rest_framework import status

from users.models import ArtistProfile, ArtistProfileType

pytestmark = pytest.mark.django_db


class TestBecomeArtistOrLabelApi:
    """Тесты создания профиля артиста или лейбла слушателем."""

    @pytest.fixture(autouse=True)
    def clear_throttle_cache(self):
        """Изолирует счётчики throttling между тестами."""
        cache.clear()
        yield
        cache.clear()

    def test_listener_becomes_artist_by_default(
        self,
        listener_client,
        listener_user,
        become_artist_url,
    ):
        """Без указания типа создается профиль артиста."""
        response = listener_client.post(
            become_artist_url,
            data={'name': 'Новый артист'},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Новый артист'
        assert response.data['profile_type'] == ArtistProfileType.ARTIST

        profile = ArtistProfile.objects.get(user=listener_user)

        assert profile.name == 'Новый артист'
        assert profile.profile_type == ArtistProfileType.ARTIST

    def test_listener_becomes_label(
        self,
        listener_client,
        listener_user,
        become_artist_url,
    ):
        """Слушатель может создать профиль лейбла."""
        response = listener_client.post(
            become_artist_url,
            data={
                'name': 'Новый лейбл',
                'profile_type': ArtistProfileType.LABEL,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Новый лейбл'
        assert response.data['profile_type'] == ArtistProfileType.LABEL

        profile = ArtistProfile.objects.get(user=listener_user)

        assert profile.name == 'Новый лейбл'
        assert profile.profile_type == ArtistProfileType.LABEL

    def test_rejects_invalid_profile_type(
        self,
        listener_client,
        listener_user,
        become_artist_url,
    ):
        """Неизвестный тип профиля отклоняется."""
        response = listener_client.post(
            become_artist_url,
            data={
                'name': 'Неизвестный профиль',
                'profile_type': 'unknown',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'profile_type' in response.data
        assert not ArtistProfile.objects.filter(
            user=listener_user,
        ).exists()

    def test_requires_authentication(
        self,
        api_client,
        become_artist_url,
    ):
        """Анонимный пользователь не может создать профиль."""
        response = api_client.post(
            become_artist_url,
            data={'name': 'Новый артист'},
            format='json',
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_independent_artist_becomes_label(
        self,
        artist_client,
        artist_user,
        become_artist_url,
    ):
        profile = artist_user.artist_profile
        original_id = profile.id
        original_name = profile.name
        original_slug = profile.slug

        response = artist_client.post(
            become_artist_url,
            data={
                'profile_type': ArtistProfileType.LABEL,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        profile.refresh_from_db()

        assert profile.id == original_id
        assert profile.profile_type == ArtistProfileType.LABEL
        assert profile.name == original_name
        assert profile.slug == original_slug
        assert profile.user == artist_user
        assert profile.label is None

    def test_becoming_label_does_not_change_artist_name(
        self,
        artist_client,
        artist_user,
        become_artist_url,
    ):
        profile = artist_user.artist_profile
        original_name = profile.name

        response = artist_client.post(
            become_artist_url,
            data={
                'profile_type': ArtistProfileType.LABEL,
                'name': 'Новое название лейбла',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        profile.refresh_from_db()

        assert profile.profile_type == ArtistProfileType.LABEL
        assert profile.name == original_name

    def test_managed_artist_cannot_become_label(
        self,
        client_factory,
        signed_artist_user,
        become_artist_url,
    ):
        client = client_factory(signed_artist_user)

        response = client.post(
            become_artist_url,
            data={
                'profile_type': ArtistProfileType.LABEL,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.data == {
            'profile_type': [
                (
                    'Нельзя стать лейблом, находясь под управлением '
                    'другого лейбла.'
                ),
            ],
        }

        signed_artist_user.artist_profile.refresh_from_db()

        assert (
            signed_artist_user.artist_profile.profile_type
            == ArtistProfileType.ARTIST
        )

    def test_existing_artist_cannot_become_artist_again(
        self,
        artist_client,
        artist_user,
        become_artist_url,
    ):
        response = artist_client.post(
            become_artist_url,
            data={
                'profile_type': ArtistProfileType.ARTIST,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.data == {
            'profile_type': [
                (
                    'У пользователя уже есть профиль артиста. '
                    'Допустим только переход к профилю лейбла.'
                ),
            ],
        }

        artist_user.artist_profile.refresh_from_db()

        assert (
            artist_user.artist_profile.profile_type == ArtistProfileType.ARTIST
        )

    @pytest.mark.parametrize(
        'profile_type',
        (
            ArtistProfileType.ARTIST,
            ArtistProfileType.LABEL,
        ),
    )
    def test_label_cannot_use_become_artist_endpoint(
        self,
        label_client,
        become_artist_url,
        profile_type,
    ):
        response = label_client.post(
            become_artist_url,
            data={'profile_type': profile_type},
            format='json',
        )

        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_artist_gets_label_permissions_after_upgrade(
        self,
        artist_client,
        artist_user,
        become_artist_url,
        label_managed_profiles_url,
    ):
        response = artist_client.post(
            become_artist_url,
            data={'profile_type': ArtistProfileType.LABEL},
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        response = artist_client.get(label_managed_profiles_url)

        assert response.status_code == HTTPStatus.OK
        assert response.data[0]['id'] == artist_user.artist_profile.id
        assert response.data[0]['is_self'] is True

    def test_name_is_required_when_creating_profile(
        self,
        auth_client,
        become_artist_url,
    ):
        response = auth_client.post(
            become_artist_url,
            data={
                'profile_type': ArtistProfileType.ARTIST,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.data == {
            'name': [
                'Это поле обязательно при создании профиля.',
            ],
        }

    def test_user_creates_artist_with_default_profile_type(
        self,
        auth_client,
        user,
        become_artist_url,
    ):
        response = auth_client.post(
            become_artist_url,
            data={
                'name': 'Новый артист',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        profile = ArtistProfile.objects.get(user=user)

        assert profile.name == 'Новый артист'
        assert profile.profile_type == ArtistProfileType.ARTIST


class TestArtistMeApi:
    """Тесты профиля текущего артиста или лейбла."""

    def test_returns_artist_profile(
        self,
        artist_client,
        artist_me_url,
    ):
        """Возвращает профиль текущего артиста."""
        response = artist_client.get(artist_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['profile_type'] == ArtistProfileType.ARTIST

    def test_returns_label_profile(
        self,
        label_client,
        artist_me_url,
    ):
        """Возвращает профиль текущего лейбла."""
        response = label_client.get(artist_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['profile_type'] == ArtistProfileType.LABEL

    def test_artist_updates_own_slug(
        self,
        artist_client,
        artist_user,
        artist_me_url,
    ):
        profile = artist_user.artist_profile
        old_slug = profile.slug

        response = artist_client.patch(
            artist_me_url,
            data={'slug': 'new-artist-address'},
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

        profile.refresh_from_db()

        assert profile.slug == 'new-artist-address'
        assert profile.slug != old_slug
        assert response.data['slug'] == 'new-artist-address'

    def test_artist_cannot_update_to_existing_slug(
        self,
        artist_client,
        artist_user,
        other_artist_user,
        artist_me_url,
    ):
        original_slug = artist_user.artist_profile.slug

        response = artist_client.patch(
            artist_me_url,
            data={
                'slug': other_artist_user.artist_profile.slug,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert 'slug' in response.data

        artist_user.artist_profile.refresh_from_db()
        assert artist_user.artist_profile.slug == original_slug

    def test_artist_cannot_set_empty_slug(
        self,
        artist_client,
        artist_user,
        artist_me_url,
    ):
        original_slug = artist_user.artist_profile.slug

        response = artist_client.patch(
            artist_me_url,
            data={'slug': ''},
            format='json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert 'slug' in response.data

        artist_user.artist_profile.refresh_from_db()
        assert artist_user.artist_profile.slug == original_slug

    def test_updating_name_does_not_change_slug(
        self,
        artist_client,
        artist_user,
        artist_me_url,
    ):
        original_slug = artist_user.artist_profile.slug

        response = artist_client.patch(
            artist_me_url,
            data={'name': 'Совершенно новое имя'},
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

        artist_user.artist_profile.refresh_from_db()
        assert artist_user.artist_profile.name == 'Совершенно новое имя'
        assert artist_user.artist_profile.slug == original_slug


class TestArtistPublicApi:
    """Тесты публичного профиля артиста или лейбла."""

    def test_returns_artist_profile_type(
        self,
        api_client,
        artist_user,
        artist_public_url,
    ):
        """Публичный профиль артиста возвращает его тип."""
        response = api_client.get(
            artist_public_url(artist_user.artist_profile),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['profile_type'] == ArtistProfileType.ARTIST

    def test_returns_label_profile_type(
        self,
        api_client,
        label_user,
        artist_public_url,
    ):
        """Публичный профиль лейбла возвращает его тип."""
        response = api_client.get(
            artist_public_url(label_user.artist_profile),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['profile_type'] == ArtistProfileType.LABEL
