"""Тесты API профилей артистов и лейблов."""

from http import HTTPStatus

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status

from store.tests.factories import AlbumFactory, GenreFactory
from users.consents_policy import ConsentPolicy, ConsentScenario
from users.models import ArtistProfile, ArtistProfileType, UserConsent
from users.tests.factories import ArtistProfileFactory

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
        artist_onboarding_consents,
    ):
        """Без указания типа создается профиль артиста."""
        response = listener_client.post(
            become_artist_url,
            data={
                'name': 'Новый артист',
                'consents': artist_onboarding_consents,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Новый артист'
        assert response.data['profile_type'] == ArtistProfileType.ARTIST

        profile = ArtistProfile.objects.get(user=listener_user)

        assert profile.name == 'Новый артист'
        assert profile.profile_type == ArtistProfileType.ARTIST

        required = ConsentPolicy.get_required(
            ConsentScenario.ARTIST_ONBOARDING,
        )

        saved_types = set(
            UserConsent.objects.filter(user=listener_user).values_list(
                'document__document_type',
                flat=True,
            ),
        )

        assert saved_types == required

    def test_listener_becomes_label(
        self,
        listener_client,
        listener_user,
        become_artist_url,
        artist_onboarding_consents,
    ):
        """Слушатель может создать профиль лейбла."""
        response = listener_client.post(
            become_artist_url,
            data={
                'name': 'Новый лейбл',
                'profile_type': ArtistProfileType.LABEL,
                'consents': artist_onboarding_consents,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Новый лейбл'
        assert response.data['profile_type'] == ArtistProfileType.LABEL

        profile = ArtistProfile.objects.get(user=listener_user)

        assert profile.name == 'Новый лейбл'
        assert profile.profile_type == ArtistProfileType.LABEL

        required = ConsentPolicy.get_required(
            ConsentScenario.LABEL_ONBOARDING,
        )

        saved_types = set(
            UserConsent.objects.filter(user=listener_user).values_list(
                'document__document_type',
                flat=True,
            ),
        )

        assert saved_types == required

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
        artist_onboarding_consents,
    ):
        response = auth_client.post(
            become_artist_url,
            data={
                'name': 'Новый артист',
                'consents': artist_onboarding_consents,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        profile = ArtistProfile.objects.get(user=user)

        assert profile.name == 'Новый артист'
        assert profile.profile_type == ArtistProfileType.ARTIST

    def test_listener_cannot_become_artist_without_consents(
        self,
        listener_client,
        listener_user,
        become_artist_url,
    ):
        """Слушатель не может стать артистом без обязательных согласий."""
        response = listener_client.post(
            become_artist_url,
            data={'name': 'Новый артист'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'consents' in response.data
        assert not ArtistProfile.objects.filter(user=listener_user).exists()

    def test_listener_cannot_become_label_without_consents(
        self,
        listener_client,
        listener_user,
        become_artist_url,
    ):
        """Слушатель не может стать лейблом без обязательных согласий."""
        response = listener_client.post(
            become_artist_url,
            data={
                'name': 'Новый лейбл',
                'profile_type': ArtistProfileType.LABEL,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'consents' in response.data
        assert not ArtistProfile.objects.filter(user=listener_user).exists()


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


@pytest.mark.usefixtures('publication_readiness_disabled')
class TestArtistListApi:
    """Тесты публичного списка артистов."""

    @pytest.fixture
    def artist_list_url(self):
        """URL публичного списка артистов."""
        return reverse('api:users:artist_list')

    def test_filter_by_genre(
        self,
        api_client,
        artist_list_url,
        artist_user,
        other_artist_user,
    ):
        """Фильтрует артистов по жанру их альбомов."""
        target_genre = GenreFactory(slug='rock')
        other_genre = GenreFactory(slug='jazz')

        AlbumFactory(
            artist=artist_user.artist_profile,
            genre=target_genre,
        )
        AlbumFactory(
            artist=other_artist_user.artist_profile,
            genre=other_genre,
        )

        response = api_client.get(
            artist_list_url,
            {'genre': target_genre.slug},
        )

        assert response.status_code == HTTPStatus.OK

        artist_ids = {item['id'] for item in response.data['results']}

        assert artist_ids == {artist_user.artist_profile.id}

    def test_filter_by_genre_returns_managed_artist_without_account(
        self,
        api_client,
        artist_list_url,
        label_user,
    ):
        """Фильтр по жанру работает для артиста без аккаунта."""
        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        genre = GenreFactory(slug='electronic')

        AlbumFactory(
            artist=artist,
            genre=genre,
            created_by=label_user,
            payout_recipient=label_user,
        )

        response = api_client.get(
            artist_list_url,
            {'genre': genre.slug},
        )

        assert response.status_code == HTTPStatus.OK

        artist_ids = {item['id'] for item in response.data['results']}

        assert artist.id in artist_ids


@pytest.mark.usefixtures('publication_readiness_enabled')
class TestArtistListReadiness:
    """Тесты готовности артистов в публичном списке."""

    @pytest.fixture
    def artist_list_url(self):
        """URL публичного списка артистов."""
        return reverse('api:users:artist_list')

    def test_list_hides_artist_without_readiness(
        self,
        api_client,
        artist_list_url,
    ):
        """Неготовый артист не отображается в публичном списке."""
        artist = ArtistProfileFactory(
            user__is_email_verified=False,
        )

        response = api_client.get(artist_list_url)

        assert response.status_code == HTTPStatus.OK

        artist_ids = {item['id'] for item in response.data['results']}

        assert artist.id not in artist_ids

    def test_list_returns_ready_artist(
        self,
        api_client,
        artist_list_url,
        ready_artist_factory,
    ):
        """Готовый артист отображается в публичном списке."""
        artist = ready_artist_factory()

        response = api_client.get(artist_list_url)

        artist_ids = {item['id'] for item in response.data['results']}

        assert artist.id in artist_ids

    def test_list_uses_label_readiness_for_managed_artist(
        self,
        api_client,
        artist_list_url,
        ready_label_factory,
    ):
        """Для управляемого артиста используется готовность лейбла."""
        label_user = ready_label_factory()

        artist = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )

        response = api_client.get(artist_list_url)

        assert response.status_code == HTTPStatus.OK

        artist_ids = {item['id'] for item in response.data['results']}

        assert artist.id in artist_ids

    @pytest.mark.usefixtures('publication_readiness_enabled')
    def test_public_profile_remains_available_without_readiness(
        self,
        api_client,
        artist_public_url,
    ):
        """Публичный профиль доступен по прямой ссылке без readiness."""
        artist = ArtistProfileFactory(
            user__is_email_verified=False,
        )

        response = api_client.get(
            artist_public_url(artist),
        )

        assert response.status_code == HTTPStatus.OK
