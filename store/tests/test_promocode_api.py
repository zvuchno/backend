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
            owner=self.artist_user,
        )
        variant_author_b = self.variant_factory(
            'album',
            price=Decimal('500.00'),
            owner=self.other_artist_user,
        )

        promocode = Promocode.objects.create(
            code='AUTHOR_A_10',
            discount_type=Promocode.DiscountType.PERCENT,
            discount_value=Decimal('10.00'),
            owner_id=self.artist_user.id,
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
                owner=self.artist_user,
            )
            for _ in range(3)
        ]

        promocode = Promocode.objects.create(
            code='FIXED_100',
            discount_type=Promocode.DiscountType.FIXED,
            discount_value=Decimal('100.00'),
            owner_id=self.artist_user.id,
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
            owner=self.artist_user,
        )
        other_variant = self.variant_factory(
            'merch',
            price=Decimal('1500.00'),
            owner=self.other_artist_user,
        )

        promocode = Promocode.objects.create(
            code='ARTIST_500',
            discount_type=Promocode.DiscountType.FIXED,
            discount_value=Decimal('500.00'),
            owner_id=self.artist_user.id,
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
