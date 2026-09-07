"""Тесты механизма удаления контента."""

import pytest
from django.urls import reverse
from rest_framework import status

from store.models import Merch, Product, ProductVariant


@pytest.mark.django_db
class TestDeletion:
    """Тесты удаления контента."""

    def test_physical_delete_cascade(self, variant_factory):
        """Физическое удаление → удаляется вся цепочка."""
        variant_merch = variant_factory('merch')
        product = variant_merch.product
        merch = getattr(product, 'merch', None)
        merch_id = merch.id
        prod_id = product.id

        merch.delete()

        assert not Merch.objects.filter(id=merch_id).exists()
        assert not Product.objects.filter(id=prod_id).exists()
        assert not ProductVariant.objects.filter(product_id=prod_id).exists()

    @pytest.mark.parametrize(
        ('factory_attr', 'url_resource_name'),
        [
            ('album', 'albums'),
            ('track', 'tracks'),
            ('merch', 'merch'),
        ],
    )
    def test_soft_delete_deactivates_object_and_variants(
        self,
        artist_client,
        variant_factory,
        factory_attr,
        url_resource_name,
    ):
        """Удаление через API → деактивация контента и его вариантов."""
        variant = variant_factory(factory_attr)
        product = variant.product
        content = getattr(product, factory_attr)

        url = reverse(
            f'api:store:{url_resource_name}-detail',
            args=[content.pk],
        )

        response = artist_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        content.refresh_from_db()
        assert content.is_active is False

        variants = product.variants.all()
        assert variants.exists()
        for v in variants:
            v.refresh_from_db()
            assert v.is_active is False
