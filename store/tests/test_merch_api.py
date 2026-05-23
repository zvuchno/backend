"""Тесты CRUD API мерча."""

import pytest
from django.urls import reverse
from rest_framework import status

from store.constants import CHAR_PRESET_SIMPLE
from store.models import Merch


@pytest.mark.django_db
class TestMerchList:
    """Тесты GET /merch/ — список мерча."""

    @pytest.fixture
    def merch_list_url(self):
        return reverse('api:store:merch-list')

    @pytest.fixture
    def merch(self, variant_factory):
        return variant_factory(
            product_type='merch',
            name='T-Shirt',
        ).product.merch

    def test_list_returns_200(self, merch, merch_list_url, api_client):
        """Список мерча доступен анонимно."""
        response = api_client.get(merch_list_url)
        assert response.status_code == status.HTTP_200_OK

    def test_list_contains_published_merch(
        self,
        merch,
        merch_list_url,
        api_client,
    ):
        """Опубликованный мерч отображается в списке."""
        response = api_client.get(merch_list_url)
        ids = [item['id'] for item in response.data['results']]
        assert merch.id in ids

    def test_list_excludes_inactive_merch(
        self,
        variant_factory,
        merch_list_url,
        api_client,
    ):
        """Неактивный мерч не отображается."""
        variant_factory(product_type='merch', name='Hidden', is_active=False)
        response = api_client.get(merch_list_url)
        names = [item['name'] for item in response.data['results']]
        assert 'Hidden' not in names

    def test_list_excludes_unpublished_merch(
        self,
        variant_factory,
        merch_list_url,
        api_client,
    ):
        """Неопубликованный мерч не отображается анонимному пользователю."""
        variant_factory(product_type='merch', name='Draft', is_published=False)
        response = api_client.get(merch_list_url)
        names = [item['name'] for item in response.data['results']]
        assert 'Draft' not in names


@pytest.mark.django_db
class TestMerchRetrieve:
    """Тесты GET /merch/{id}/ — детальный просмотр."""

    @pytest.fixture
    def merch(self, variant_factory):
        return variant_factory(
            product_type='merch',
            name='T-Shirt',
        ).product.merch

    @pytest.fixture
    def merch_detail_url(self, merch):
        return reverse('api:store:merch-detail', kwargs={'pk': merch.pk})

    def test_retrieve_returns_200(self, merch_detail_url, api_client):
        """Детальный просмотр доступен анонимно."""
        response = api_client.get(merch_detail_url)
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_contains_expected_fields(
        self,
        merch_detail_url,
        api_client,
    ):
        """Ответ содержит нужные поля."""
        response = api_client.get(merch_detail_url)
        for field in (
            'id',
            'name',
            'price',
            'variants',
            'images_merch',
            'stock',
        ):
            assert field in response.data

    def test_retrieve_inactive_returns_404(self, variant_factory, api_client):
        """Неактивный мерч возвращает 404."""
        variant = variant_factory(product_type='merch', is_active=False)
        url = reverse(
            'api:store:merch-detail',
            kwargs={'pk': variant.product.merch.pk},
        )
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestMerchCreate:
    """Тесты POST /merch/ — создание мерча."""

    @pytest.fixture
    def merch_list_url(self):
        return reverse('api:store:merch-list')

    @pytest.fixture
    def merch_payload(self):
        return {
            'name': 'New Merch',
            'description': 'Cool merch',
            'price': '999.00',
            'stock': 10,
            'visibility': 'public',
            'is_published': True,
        }

    def test_artist_can_create_merch(
        self,
        merch_payload,
        merch_list_url,
        artist_client,
    ):
        """Артист может создать мерч."""
        response = artist_client.post(
            merch_list_url,
            merch_payload,
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Merch.objects.filter(name='New Merch').exists()

    def test_create_merch_creates_simple_variant(
        self,
        merch_payload,
        merch_list_url,
        artist_client,
    ):
        """При создании без вариантов создаётся simple вариант."""
        artist_client.post(merch_list_url, merch_payload, format='json')
        merch = Merch.objects.get(name='New Merch')
        assert merch.product.variants.filter(
            property_value=CHAR_PRESET_SIMPLE,
            is_active=True,
        ).exists()

    def test_anonymous_cannot_create_merch(
        self,
        merch_payload,
        merch_list_url,
        api_client,
    ):
        """Анонимный пользователь не может создать мерч."""
        response = api_client.post(
            merch_list_url,
            merch_payload,
            format='json',
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_merch_with_variants(self, merch_list_url, artist_client):
        """Создание мерча с вариантами."""
        payload = {
            'name': 'Merch With Variants',
            'price': '500.00',
            'property_name': 'size',
            'variants': [
                {'value': 'S', 'stock': 10},
                {'value': 'M', 'stock': 20},
            ],
        }
        response = artist_client.post(merch_list_url, payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        merch = Merch.objects.get(name='Merch With Variants')
        assert (
            merch.product.variants
            .filter(is_active=True)
            .exclude(
                property_value=CHAR_PRESET_SIMPLE,
            )
            .count()
            == 2
        )


@pytest.mark.django_db
class TestMerchUpdate:
    """Тесты PATCH /merch/{id}/ — обновление мерча."""

    @pytest.fixture
    def merch(self, variant_factory, artist_user):
        return variant_factory(
            product_type='merch',
            name='T-Shirt',
            owner=artist_user,
        ).product.merch

    @pytest.fixture
    def merch_detail_url(self, merch):
        return reverse('api:store:merch-detail', kwargs={'pk': merch.pk})

    def test_owner_can_update_merch(self, merch_detail_url, artist_client):
        """Владелец может обновить мерч."""
        response = artist_client.patch(
            merch_detail_url,
            {'name': 'Updated'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated'

    def test_other_artist_cannot_update_merch(
        self,
        merch_detail_url,
        other_artist_client,
    ):
        """Чужой артист не может обновить мерч."""
        response = other_artist_client.patch(
            merch_detail_url,
            {'name': 'Hacked'},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_anonymous_cannot_update_merch(self, merch_detail_url, api_client):
        """Анонимный пользователь не может обновить мерч."""
        response = api_client.patch(
            merch_detail_url,
            {'name': 'Hacked'},
            format='json',
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_deactivate_variants_clears_property_name(
        self,
        merch,
        merch_detail_url,
        artist_client,
    ):
        """variants=[] → property_name обнуляется."""
        artist_client.patch(
            merch_detail_url,
            {
                'property_name': 'size',
                'variants': [{'value': 'S', 'stock': 10}],
            },
            format='json',
        )
        response = artist_client.patch(
            merch_detail_url,
            {'variants': []},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        merch.refresh_from_db()
        assert merch.product.property_name == ''


@pytest.mark.django_db
class TestMerchDelete:
    """Тесты DELETE /merch/{id}/ — удаление мерча."""

    @pytest.fixture
    def merch(self, variant_factory, artist_user):
        return variant_factory(
            product_type='merch',
            owner=artist_user,
        ).product.merch

    @pytest.fixture
    def merch_detail_url(self, merch):
        return reverse('api:store:merch-detail', kwargs={'pk': merch.pk})

    def test_owner_can_delete_merch(
        self,
        merch,
        merch_detail_url,
        artist_client,
    ):
        """Владелец может удалить мерч (мягкое удаление)."""
        response = artist_client.delete(merch_detail_url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        merch.refresh_from_db()
        assert merch.is_active is False

    def test_other_artist_cannot_delete_merch(
        self,
        merch_detail_url,
        other_artist_client,
    ):
        """Чужой артист не может удалить мерч."""
        response = other_artist_client.delete(merch_detail_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_anonymous_cannot_delete_merch(self, merch_detail_url, api_client):
        """Анонимный пользователь не может удалить мерч."""
        response = api_client.delete(merch_detail_url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_deleted_merch_not_in_list(self, merch, artist_client):
        """Удалённый мерч не отображается в списке."""
        url = reverse('api:store:merch-detail', kwargs={'pk': merch.pk})
        artist_client.delete(url)
        list_url = reverse('api:store:merch-list')
        response = artist_client.get(list_url)
        ids = [item['id'] for item in response.data['results']]
        assert merch.id not in ids
