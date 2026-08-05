from http import HTTPStatus

import pytest

from users.models import ArtistProfile, ArtistProfileType


@pytest.mark.django_db
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
        artist_user_factory,
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
