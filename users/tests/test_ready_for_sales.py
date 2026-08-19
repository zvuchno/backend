"""Тесты готовности артиста к публикации товаров."""

import pytest
from rest_framework import status

from common.services import (
    PublicationRequirement,
    get_artist_publication_readiness,
)

from users.tests.factories import ArtistProfileFactory

pytestmark = pytest.mark.django_db


@pytest.mark.usefixtures('publication_readiness_enabled')
class TestArtistPublicationReadiness:
    """Тесты готовности артиста к публикации товаров."""

    def test_unverified_email_blocks_all_publication(self):
        """Неподтвержденный email блокирует публикацию товаров."""
        artist = ArtistProfileFactory(
            user__is_email_verified=False,
        )

        readiness = get_artist_publication_readiness(artist)

        assert readiness.can_publish_digital is False
        assert readiness.can_publish_physical is False
        assert (
            PublicationRequirement.EMAIL_VERIFICATION
            in readiness.digital_missing
        )

    def test_unverified_legal_profile_blocks_all_publication(
        self,
        artist_legal_profile_factory,
    ):
        """Неверифицированный юрпрофиль блокирует публикацию."""
        artist = ArtistProfileFactory(
            user__is_email_verified=True,
        )

        artist_legal_profile_factory(
            artist.user,
            is_verified=False,
        )

        readiness = get_artist_publication_readiness(artist)

        assert readiness.can_publish_digital is False
        assert readiness.can_publish_physical is False
        assert (
            PublicationRequirement.LEGAL_PROFILE_VERIFICATION
            in readiness.digital_missing
        )

    def test_shipping_point_blocks_only_physical_publication(
        self,
        ready_artist_factory,
    ):
        """Отсутствие ПВЗ блокирует только физические товары."""
        artist = ready_artist_factory()

        readiness = get_artist_publication_readiness(artist)

        assert readiness.can_publish_digital is True
        assert readiness.can_publish_physical is False
        assert readiness.digital_missing == ()
        assert readiness.physical_missing == (
            PublicationRequirement.SHIPPING_POINT,
        )

    def test_artist_me_contains_publication_readiness(
        self,
        auth_client,
        artist_me_url,
        artist_legal_profile_factory,
    ):
        """Профиль артиста содержит состояние готовности к публикации."""
        artist = ArtistProfileFactory(
            user__is_email_verified=True,
        )

        artist_legal_profile_factory(
            artist.user,
            is_verified=True,
        )

        auth_client.force_authenticate(user=artist.user)

        response = auth_client.get(artist_me_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['publication_readiness'] == {
            'digital': {
                'can_publish': True,
                'missing_requirements': [],
            },
            'physical': {
                'can_publish': False,
                'missing_requirements': ['shipping_point'],
            },
        }


def test_publication_readiness_can_be_disabled(
    publication_readiness_disabled,
):
    """Отключённая проверка разрешает публикацию без верификации."""
    artist = ArtistProfileFactory(
        user__is_email_verified=False,
    )

    readiness = get_artist_publication_readiness(artist)

    assert readiness.can_publish_digital is True
    assert readiness.can_publish_physical is True
    assert readiness.digital_missing == ()
    assert readiness.physical_missing == ()
