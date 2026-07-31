"""Тесты API мерча."""

from io import BytesIO

import pytest
from PIL import Image as PILImage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from store.constants import CHAR_PRESET_SIMPLE
from store.models import Merch


def make_image(name='test.jpg'):
    """Создаёт валидное изображение для загрузки."""
    img = PILImage.new('RGB', (10, 10), color='red')
    buf = BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type='image/jpeg')


@pytest.mark.django_db
class TestMerchCreate:
    """Тесты POST /merch/ — создание мерча."""

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
            .exclude(property_value=CHAR_PRESET_SIMPLE)
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
class TestMerchImages:
    """Тесты работы с изображениями мерча."""

    @pytest.fixture
    def merch(self, variant_factory, artist_user):
        return variant_factory(
            product_type='merch',
            owner=artist_user,
        ).product.merch

    @pytest.fixture
    def add_image_url(self, merch):
        return reverse('api:store:merch-add-image', kwargs={'pk': merch.pk})

    @pytest.fixture
    def merch_detail_url(self, merch):
        return reverse('api:store:merch-detail', kwargs={'pk': merch.pk})

    def test_first_image_becomes_main(self, add_image_url, artist_client):
        """Первое добавленное изображение становится главным."""
        response = artist_client.post(
            add_image_url,
            {'image': make_image()},
            format='multipart',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['is_main'] is True

    def test_second_image_not_main(self, add_image_url, artist_client):
        """Второе изображение не становится главным автоматически."""
        first_response = artist_client.post(
            add_image_url,
            {'image': make_image('a.jpg')},
            format='multipart',
        )
        response = artist_client.post(
            add_image_url,
            {'image': make_image('b.jpg')},
            format='multipart',
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert first_response.data['is_main'] is True
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['is_main'] is False

    def test_delete_main_image_promotes_next(
        self,
        merch,
        add_image_url,
        merch_detail_url,
        artist_client,
    ):
        """Удаление главного изображения назначает следующим главное."""
        first_response = artist_client.post(
            add_image_url,
            {'image': make_image('a.jpg')},
            format='multipart',
        )
        second_response = artist_client.post(
            add_image_url,
            {'image': make_image('b.jpg')},
            format='multipart',
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert second_response.status_code == status.HTTP_201_CREATED

        delete_url = reverse(
            'api:store:merch-image-detail',
            kwargs={
                'pk': merch.pk,
                'image_id': first_response.data['id'],
            },
        )
        response = artist_client.delete(delete_url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        response = artist_client.get(merch_detail_url)

        assert response.status_code == status.HTTP_200_OK

        main_images = [
            image
            for image in response.data['images_merch']
            if image['is_main']
        ]

        assert len(main_images) == 1
        assert main_images[0]['id'] == second_response.data['id']

    def test_patch_main_false_promotes_next(
        self,
        merch,
        add_image_url,
        merch_detail_url,
        artist_client,
    ):
        """Снятие главного статуса назначает следующим главное."""
        first_response = artist_client.post(
            add_image_url,
            {'image': make_image('a.jpg')},
            format='multipart',
        )
        second_response = artist_client.post(
            add_image_url,
            {'image': make_image('b.jpg')},
            format='multipart',
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert second_response.status_code == status.HTTP_201_CREATED

        patch_url = reverse(
            'api:store:merch-image-detail',
            kwargs={
                'pk': merch.pk,
                'image_id': first_response.data['id'],
            },
        )
        response = artist_client.patch(
            patch_url,
            {'is_main': False},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_main'] is False

        response = artist_client.get(merch_detail_url)

        assert response.status_code == status.HTTP_200_OK

        main_images = [
            image
            for image in response.data['images_merch']
            if image['is_main']
        ]

        assert len(main_images) == 1
        assert main_images[0]['id'] == second_response.data['id']

    def test_only_image_remains_main_when_main_status_is_removed(
        self,
        merch,
        add_image_url,
        merch_detail_url,
        artist_client,
    ):
        """Единственное изображение нельзя оставить без главного статуса."""
        create_response = artist_client.post(
            add_image_url,
            {'image': make_image()},
            format='multipart',
        )

        assert create_response.status_code == status.HTTP_201_CREATED
        assert create_response.data['is_main'] is True

        patch_url = reverse(
            'api:store:merch-image-detail',
            kwargs={
                'pk': merch.pk,
                'image_id': create_response.data['id'],
            },
        )
        response = artist_client.patch(
            patch_url,
            {'is_main': False},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_main'] is True

        response = artist_client.get(merch_detail_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['images_merch'][0]['is_main'] is True

    def test_explicit_is_main_true_on_second_image(
        self,
        merch,
        add_image_url,
        merch_detail_url,
        artist_client,
    ):
        """Явное назначение второго изображения снимает статус с первого."""
        first_response = artist_client.post(
            add_image_url,
            {'image': make_image('a.jpg')},
            format='multipart',
        )
        second_response = artist_client.post(
            add_image_url,
            {'image': make_image('b.jpg'), 'is_main': True},
            format='multipart',
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert second_response.status_code == status.HTTP_201_CREATED
        assert second_response.data['is_main'] is True

        response = artist_client.get(merch_detail_url)

        assert response.status_code == status.HTTP_200_OK

        main_images = [
            image
            for image in response.data['images_merch']
            if image['is_main']
        ]

        assert len(main_images) == 1
        assert main_images[0]['id'] == second_response.data['id']

        first_image = next(
            image
            for image in response.data['images_merch']
            if image['id'] == first_response.data['id']
        )

        assert first_image['is_main'] is False


@pytest.mark.django_db
class TestMerchVariants:
    """Тесты работы с вариантами мерча."""

    @pytest.fixture
    def merch(self, variant_factory, artist_user):
        return variant_factory(
            product_type='merch',
            owner=artist_user,
        ).product.merch

    @pytest.fixture
    def merch_detail_url(self, merch):
        return reverse('api:store:merch-detail', kwargs={'pk': merch.pk})

    def test_merch_detail_hidden_from_non_owner_and_anonymous(
        self,
        merch,
        merch_detail_url,
        other_artist_client,
        api_client,
    ):
        """Мерч недоступен для чужого артиста и анонимного пользователя."""
        response_other_artist = other_artist_client.get(merch_detail_url)
        assert response_other_artist.status_code == status.HTTP_404_NOT_FOUND

        response_anonymous = api_client.get(merch_detail_url)
        assert response_anonymous.status_code == status.HTTP_401_UNAUTHORIZED

    def test_cannot_update_variant_of_other_merch(
        self,
        merch,
        merch_detail_url,
        artist_client,
        variant_factory,
        artist_user,
    ):
        """Нельзя передать ID варианта чужого мерча."""
        other_merch = variant_factory(
            product_type='merch',
            owner=artist_user,
        ).product.merch
        other_variant_id = other_merch.product.variants.first().id

        response = artist_client.patch(
            merch_detail_url,
            {
                'variants': [
                    {'id': other_variant_id, 'value': 'S', 'stock': 10},
                ],
            },
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_variants_deactivated_when_merch_inactive(
        self,
        merch,
        merch_detail_url,
        artist_client,
    ):
        """При деактивации мерча варианты деактивируются."""
        artist_client.patch(
            merch_detail_url,
            {'variants': [{'value': 'S', 'stock': 10}]},
            format='json',
        )
        artist_client.delete(merch_detail_url)
        merch.refresh_from_db()
        assert merch.product.variants.filter(is_active=True).count() == 0
