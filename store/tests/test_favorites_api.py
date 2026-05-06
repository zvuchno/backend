"""Тесты для избранного пользователя."""

from django.urls import reverse
from rest_framework import status

from store.models import Favorite


class TestFavoritesAPI:
    """Набор тестов для проверки функциональности избранного."""

    def test_add_to_favorites(
        self,
        auth_client,
        favorites_url,
        variant_factory,
        user,
    ):
        """Добавление варианта продукта в избранное."""
        variant = variant_factory()

        response = auth_client.post(
            favorites_url,
            data={'product_variant': variant.id},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Favorite.objects.filter(
            user=user,
            product_variant=variant,
        ).exists()
        assert response.data['product_variant'] == variant.id

    def test_get_favorites_list(
        self,
        auth_client,
        other_client,
        favorites_url,
        variant_factory,
    ):
        """Каждый пользователь видит только свое избранное."""
        variant = variant_factory()
        auth_client.post(
            favorites_url,
            data={'product_variant': variant.id},
            format='json',
        )

        response = auth_client.get(favorites_url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['product_variant'] == variant.id

        response = other_client.get(favorites_url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 0

    def test_remove_from_favorites(
        self,
        auth_client,
        favorites_url,
        variant_factory,
    ):
        """Проверяет удаление записи из избранного."""
        variant = variant_factory()
        res_create = auth_client.post(
            favorites_url,
            data={'product_variant': variant.id},
            format='json',
        )
        favorite_id = res_create.data['id']

        url = reverse('api:store:me-favorites-detail', args=[favorite_id])
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Favorite.objects.filter(id=favorite_id).exists()

    def test_prevent_duplicate_favorites(
        self,
        auth_client,
        favorites_url,
        variant_factory,
        user,
    ):
        """Проверяет работу UniqueTogetherValidator в сериализаторе."""
        variant = variant_factory()
        payload = {
            'product_variant': variant.id,
        }
        auth_client.post(favorites_url, data=payload, format='json')
        response = auth_client.post(favorites_url, data=payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'non_field_errors' in response.data or (
            'product_variant' in response.data
        )
