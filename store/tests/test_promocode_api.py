from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from store.models import Cart, Promocode


class TestPromocodeAPI:
    """Набор тестов для логики промокодов в корзине."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        auth_client,
        artist_user,
        other_artist_user,
        apply_promocode_url,
        cart_add_url,
        variant_factory,
    ) -> None:
        """Автоматически прокидывает зависимости в self перед каждым тестом."""
        self.auth_client = auth_client
        self.artist_user = artist_user
        self.other_artist_user = other_artist_user
        self.apply_promocode_url = apply_promocode_url
        self.cart_add_url = cart_add_url
        self.variant_factory = variant_factory

    def test_cart_percentage_promocode_applicable_only_to_owner_products(
        self,
    ):
        """Промокод применяется только к товарам его автора."""
        variant_author_a = self.variant_factory(
            'merch',
            price=Decimal('1000.00'),
            artist=self.artist_user.artist_profile,
        )
        variant_author_b = self.variant_factory(
            'album',
            price=Decimal('500.00'),
            artist=self.other_artist_user.artist_profile,
        )

        promocode = Promocode.objects.create(
            code='AUTHOR_A_10',
            discount_type=Promocode.DiscountType.PERCENT,
            discount_value=Decimal('10.00'),
            artist=self.artist_user.artist_profile,
            created_by=self.artist_user,
        )

        self.auth_client.post(
            self.cart_add_url,
            data={'product_variant': variant_author_a.id, 'quantity': 2},
            format='json',
        )
        self.auth_client.post(
            self.cart_add_url,
            data={'product_variant': variant_author_b.id, 'quantity': 1},
            format='json',
        )

        response = self.auth_client.post(
            self.apply_promocode_url,
            data={'code': promocode.code},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()

        item_a = next(
            item
            for item in data['items']
            if item['product_variant'] == variant_author_a.id
        )
        item_b = next(
            item
            for item in data['items']
            if item['product_variant'] == variant_author_b.id
        )

        assert Decimal(item_a['base_line_total']) == Decimal('2000.00')
        assert Decimal(item_a['discount_line_total']) == Decimal('1800.00')
        assert Decimal(item_b['base_line_total']) == Decimal('500.00')
        assert Decimal(item_b['discount_line_total']) == Decimal('500.00')

    def test_cart_fixed_promocode_distribution_prevents_penny_loss(
        self,
    ):
        """Фикс.скидка распределяется между позициями без потери копеек."""
        variants = [
            self.variant_factory(
                'merch',
                price=Decimal('100.00'),
                artist=self.artist_user.artist_profile,
            )
            for _ in range(3)
        ]

        promocode = Promocode.objects.create(
            code='FIXED_100',
            discount_type=Promocode.DiscountType.FIXED,
            discount_value=Decimal('100.00'),
            artist=self.artist_user.artist_profile,
            created_by=self.artist_user,
        )

        for variant in variants:
            self.auth_client.post(
                self.cart_add_url,
                data={'product_variant': variant.id, 'quantity': 1},
                format='json',
            )

        response = self.auth_client.post(
            self.apply_promocode_url,
            data={'code': promocode.code},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert Decimal(data['subtotal']) == Decimal('300.00')
        assert Decimal(data['discount_promocode']) == Decimal('100.00')
        assert Decimal(data['total']) == Decimal('200.00')

        total_items_discount = sum(
            Decimal(item['base_line_total'])
            - Decimal(item['discount_line_total'])
            for item in data['items']
        )
        assert total_items_discount == Decimal('100.00')

        # Проверяем распределение 100 рублей на 3 товара
        discounts = sorted([
            Decimal(item['base_line_total'])
            - Decimal(item['discount_line_total'])
            for item in data['items']
        ])
        assert discounts == [
            Decimal('33.33'),
            Decimal('33.33'),
            Decimal('33.34'),
        ]

    def test_promocode_resets_when_no_owner_products_left(
        self,
        cart_url,
        user,
    ):
        """Удалены товары владельца промокода → сброс промокода в корзине."""
        our_variant = self.variant_factory(
            'merch',
            price=Decimal('1000.00'),
            artist=self.artist_user.artist_profile,
        )
        other_variant = self.variant_factory(
            'merch',
            price=Decimal('1500.00'),
            artist=self.other_artist_user.artist_profile,
        )

        promocode = Promocode.objects.create(
            code='ARTIST_500',
            discount_type=Promocode.DiscountType.FIXED,
            discount_value=Decimal('500.00'),
            artist=self.artist_user.artist_profile,
            created_by=self.artist_user,
        )

        self.auth_client.post(
            self.cart_add_url,
            data={'product_variant': our_variant.id, 'quantity': 1},
            format='json',
        )
        self.auth_client.post(
            self.cart_add_url,
            data={'product_variant': other_variant.id, 'quantity': 1},
            format='json',
        )

        response = self.auth_client.post(
            self.apply_promocode_url,
            data={'code': promocode.code},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        assert Decimal(response.data['discount_promocode']) == (
            Decimal('500.00')
        )

        remove_url = reverse(
            'api:store:cart-remove-item',
            kwargs={'variant_id': our_variant.id},
        )
        response = self.auth_client.delete(remove_url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        response = self.auth_client.get(cart_url)
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert len(data['items']) == 1
        assert Decimal(data['discount_promocode']) == Decimal('0.00')
        user_cart = Cart.objects.get(user=user)
        assert user_cart.promocode is None


@pytest.mark.django_db
class TestPromocodeManagementAPI:
    """Тесты управления промокодами артистами и лейблами."""

    def test_artist_creates_promocode_without_artist(
        self,
        artist_client,
        artist_user,
        promocode_list_url,
    ):
        """Для артиста профиль автоматически определяется бэкендом."""
        response = artist_client.post(
            promocode_list_url,
            data={
                'code': 'ARTIST10',
                'discount_type': Promocode.DiscountType.PERCENT,
                'discount_value': '10.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        promocode = Promocode.objects.get(code='ARTIST10')

        assert promocode.artist == artist_user.artist_profile
        assert promocode.created_by == artist_user
        assert response.data['artist'] == artist_user.artist_profile.id

    def test_artist_can_explicitly_provide_own_profile(
        self,
        artist_client,
        artist_user,
        promocode_list_url,
    ):
        """Артист может явно передать собственный профиль."""
        response = artist_client.post(
            promocode_list_url,
            data={
                'artist': artist_user.artist_profile.id,
                'code': 'OWNPROFILE10',
                'discount_type': Promocode.DiscountType.PERCENT,
                'discount_value': '10.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        promocode = Promocode.objects.get(code='OWNPROFILE10')

        assert promocode.artist == artist_user.artist_profile
        assert promocode.created_by == artist_user

    def test_artist_cannot_create_promocode_for_another_artist(
        self,
        artist_client,
        other_artist_user,
        promocode_list_url,
    ):
        """Артист не может создать промокод для чужого профиля."""
        response = artist_client.post(
            promocode_list_url,
            data={
                'artist': other_artist_user.artist_profile.id,
                'code': 'FOREIGN10',
                'discount_type': Promocode.DiscountType.PERCENT,
                'discount_value': '10.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not Promocode.objects.filter(code='FOREIGN10').exists()

    def test_label_must_provide_artist(
        self,
        label_client,
        promocode_list_url,
    ):
        """Лейбл должен явно выбрать профиль для промокода."""
        response = label_client.post(
            promocode_list_url,
            data={
                'code': 'LABEL_10',
                'discount_type': Promocode.DiscountType.PERCENT,
                'discount_value': '10.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'artist' in response.data
        assert not Promocode.objects.filter(code='LABEL_10').exists()

    def test_label_creates_promocode_for_managed_artist(
        self,
        label_client,
        label_user,
        label_created_artist,
        promocode_list_url,
    ):
        """Лейбл создаёт промокод для управляемого артиста."""
        response = label_client.post(
            promocode_list_url,
            data={
                'artist': label_created_artist.id,
                'code': 'MANAGED10',
                'discount_type': Promocode.DiscountType.PERCENT,
                'discount_value': '10.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        promocode = Promocode.objects.get(code='MANAGED10')

        assert promocode.artist == label_created_artist
        assert promocode.created_by == label_user
        assert response.data['artist'] == label_created_artist.id

    def test_label_creates_promocode_for_signed_artist(
        self,
        label_client,
        label_user,
        signed_artist_user,
        promocode_list_url,
    ):
        """Лейбл создаёт промокод для подключённого артиста."""
        response = label_client.post(
            promocode_list_url,
            data={
                'artist': signed_artist_user.artist_profile.id,
                'code': 'SIGNED10',
                'discount_type': Promocode.DiscountType.PERCENT,
                'discount_value': '10.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        promocode = Promocode.objects.get(code='SIGNED10')

        assert promocode.artist == signed_artist_user.artist_profile
        assert promocode.created_by == label_user

    def test_label_cannot_create_promocode_for_unmanaged_artist(
        self,
        label_client,
        other_artist_user,
        promocode_list_url,
    ):
        """Лейбл не может создать промокод чужого артиста."""
        response = label_client.post(
            promocode_list_url,
            data={
                'artist': other_artist_user.artist_profile.id,
                'code': 'UNMANAGED10',
                'discount_type': Promocode.DiscountType.PERCENT,
                'discount_value': '10.00',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not Promocode.objects.filter(code='UNMANAGED10').exists()
