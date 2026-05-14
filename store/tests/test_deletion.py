"""Тесты механизма гибридного удаления контента."""

import pytest

from store.models import Merch, Order, OrderItem, Product, ProductVariant
from store.services import ProductService


@pytest.mark.django_db
class TestDeletion:
    """Тесты гибридного удаления контента."""

    @pytest.fixture
    def merch_setup(self, user):
        """Фикстура для создания мерча с продуктом и вариантами."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)
        product = ProductService.ensure_commerce(
            merch,
            validated_data={
                'variants': [
                    {'property_value': 'S', 'stock': 10},
                    {'property_value': 'L', 'stock': 5},
                ],
            },
        )
        return merch, product

    def test_hard_delete_when_no_orders(self, merch_setup):
        """Мерч без заказа → вся цепочка удаляется физически."""
        merch, product = merch_setup

        assert product.variants.filter(is_active=True).count() == 2

        merch_id = merch.id
        prod_id = product.id

        merch.delete()

        assert not Merch.objects.filter(id=merch_id).exists()
        assert not Product.objects.filter(id=prod_id).exists()
        assert not ProductVariant.objects.filter(product_id=prod_id).exists()

    def test_hybrid_delete_with_orders(self, merch_setup, user):
        """Мерч с заказом → деактивация мерча и его вариантов."""
        merch, product = merch_setup
        variant = product.variants.first()

        assert product.variants.filter(is_active=True).count() == 2

        order = Order.objects.create(
            user=user,
            full_name='Test User',
            email='test@email.com',
            phone='89445654785',
        )
        OrderItem.objects.create(
            order=order,
            product_variant=variant,
            quantity=1,
        )

        merch.delete()

        merch.refresh_from_db()
        assert merch.is_active is False
        assert product.variants.filter(is_active=True).count() == 0
        assert product.variants.filter(is_active=False).count() == 2
