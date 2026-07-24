from http import HTTPStatus

import pytest

from users.models import ArtistProfileType


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
        profiles = response.data['results']

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

        profiles = response.data['results']

        assert response.data['count'] == 2
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
