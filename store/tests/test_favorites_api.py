"""Тесты для избранного пользователя."""

import pytest
from django.urls import reverse
from rest_framework import status

from store.models import Favorite


@pytest.mark.django_db
class TestFavoritesAPI:
    """Набор тестов для проверки функциональности избранного."""

    @pytest.fixture(autouse=True)
    def _setup(self, auth_client, favorites_url, variant_factory) -> None:
        """Автоматически прокидывает зависимости в self перед каждым тестом."""
        self.auth_client = auth_client
        self.favorites_url = favorites_url
        self.variant_factory = variant_factory

    def test_add_to_favorites(self, user):
        """Добавление варианта продукта в избранное."""
        variant = self.variant_factory()

        response = self.auth_client.post(
            self.favorites_url,
            data={'product_variant': variant.id},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Favorite.objects.filter(
            user=user,
            product_variant=variant,
        ).exists()
        assert response.data['product_variant'] == variant.id

    def test_get_favorites_list(self, other_client):
        """Каждый пользователь видит только свое избранное."""
        variant = self.variant_factory()
        self.auth_client.post(
            self.favorites_url,
            data={'product_variant': variant.id},
            format='json',
        )

        response = self.auth_client.get(self.favorites_url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['product_variant'] == variant.id

        response = other_client.get(self.favorites_url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 0

    def test_remove_from_favorites(self):
        """Проверяет удаление записи из избранного."""
        variant = self.variant_factory()
        res_create = self.auth_client.post(
            self.favorites_url,
            data={'product_variant': variant.id},
            format='json',
        )
        favorite_id = res_create.data['id']

        url = reverse('api:store:me-favorites-detail', args=[favorite_id])
        response = self.auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Favorite.objects.filter(id=favorite_id).exists()

    def test_prevent_duplicate_favorites(self):
        """Проверяет работу UniqueTogetherValidator в сериализаторе."""
        variant = self.variant_factory()
        payload = {'product_variant': variant.id}

        self.auth_client.post(self.favorites_url, data=payload, format='json')
        response = self.auth_client.post(
            self.favorites_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'non_field_errors' in response.data or (
            'product_variant' in response.data
        )
