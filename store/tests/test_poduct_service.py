"""Тесты логики коммерческой обвязки контента (обновленная версия)."""

from decimal import Decimal

import pytest

from store.constants import CHAR_PRESET_DIGITAL, CHAR_PRESET_SIMPLE
from store.models import Album, Merch, Product
from store.services import ProductService


@pytest.mark.django_db
class TestProductService:
    """Тесты orchestration-логики ensure_commerce."""

    def test_ensure_commerce_creates_album_with_digital_variant(self, user):
        """Album → создается продукт + digital вариант."""
        album = Album.objects.create(
            name='Test Album',
            owner=user,
        )

        product = ProductService.ensure_commerce(album, validated_data={})

        assert isinstance(product, Product)
        assert product.album == album

        variant = product.variants.get()
        assert variant.property_value == CHAR_PRESET_DIGITAL
        assert variant.stock is None

    def test_ensure_commerce_idempotency(self, variant_factory):
        """Повторный вызов не создает дубликаты."""
        variant = variant_factory(product_type='track')
        product_existing = variant.product
        track = product_existing.track

        product_returned = ProductService.ensure_commerce(
            track,
            validated_data={},
        )

        assert product_returned.pk == product_existing.pk
        assert Product.objects.filter(track=track).count() == 1
        assert product_returned.variants.count() == 1

    def test_ensure_commerce_updates_product_fields(self, user):
        """Поля продукта обновляются внутри ensure_commerce."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)

        product = ProductService.ensure_commerce(
            merch,
            validated_data={
                'price': 100,
                'allow_overpay': False,
                'property_name': 'Size',
                'stock': 10,
                'variants': None,
            },
        )

        assert Decimal(product.price) == Decimal('100')
        assert product.allow_overpay is False
        assert product.property_name == 'Size'

    def test_ensure_commerce_creates_simple_merch(self, user):
        """Merch без вариантов → создается SIMPLE вариант."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)

        product = ProductService.ensure_commerce(
            merch,
            validated_data={
                'stock': 50,
                'variants': None,
            },
        )

        variant = product.variants.get(is_active=True)

        assert variant.property_value == CHAR_PRESET_SIMPLE
        assert variant.stock == 50
        assert product.variants.count() == 1

    def test_ensure_commerce_creates_variants_merch(self, user):
        """Merch с вариантами → создаются варианты."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)

        product = ProductService.ensure_commerce(
            merch,
            validated_data={
                'stock': 0,
                'variants': [
                    {'property_value': 'S', 'stock': 10},
                    {'property_value': 'L', 'stock': 5},
                ],
            },
        )

        active = product.variants.filter(is_active=True)
        assert active.count() == 2
        assert active.get(property_value='S').stock == 10
        assert active.get(property_value='L').stock == 5


@pytest.mark.django_db
class TestSyncMerchVariants:
    """Тесты логики sync_merch_variants."""

    def test_transition_complex_to_simple(self, user):
        """Сложный мерч → простой: старые варианты деактивируются."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)
        product = ProductService.ensure_commerce(merch, validated_data={})

        # Сначала делаем сложный товар

        ProductService.sync_merch_variants(
            product,
            0,
            [
                {'property_value': 'S', 'stock': 10},
                {'property_value': 'M', 'stock': 20},
            ],
        )
        # Переводим в простой товар (variants=None)
        ProductService.sync_merch_variants(product, 100, None)

        # Проверяем: активен только один, остальные выключены
        assert product.variants.filter(is_active=True).count() == 1
        assert product.variants.get(is_active=True).stock == 100
        assert product.variants.filter(is_active=False).count() == 2

    def test_update_variant_by_id(self, user):
        """ID в списке → обновление существующего варианта без дублирования."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)
        # Создаем начальный вариант
        product = ProductService.ensure_commerce(
            merch,
            validated_data={
                'variants': [{'property_value': 'Blue', 'stock': 5}],
                'stock': 0,
            },
        )

        variant_id = product.variants.get(property_value='Blue').id

        # Обновляем тот же вариант по ID
        ProductService.sync_merch_variants(
            product,
            0,
            [{'id': variant_id, 'property_value': 'Red', 'stock': 15}],
        )
        # Проверяем, что ID тот же, а данные новые
        variant = product.variants.get(property_value='Red')
        assert variant.id == variant_id
        assert variant.property_value == 'Red'
        assert variant.stock == 15

    def test_partial_sync(self, user):
        """Неполный список → варианты, отсутствующие в списке, выключаются."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)

        product = ProductService.ensure_commerce(
            merch,
            validated_data={
                'variants': [
                    {'property_value': '1', 'stock': 1},
                    {'property_value': '2', 'stock': 2},
                ],
            },
        )

        ProductService.sync_merch_variants(
            product,
            0,
            [{'property_value': '3', 'stock': 3}],
        )

        assert product.variants.filter(is_active=True).count() == 1
        assert product.variants.filter(is_active=False).count() == 2

    def test_no_duplicates(self, user):
        """Дубли в списке → остается одна запись с последним стоком."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)
        product = ProductService.ensure_commerce(
            merch,
            validated_data={
                'variants': [
                    {'property_value': 'S', 'stock': 10},
                    {'property_value': 'S', 'stock': 20},
                ],
            },
        )

        assert product.variants.filter(is_active=True).count() == 1
        assert product.variants.get(property_value='S').stock == 20

    def test_reactivate_variant(self, user):
        """Повторный ввод данных → неактивный вариант снова включается."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)
        product = ProductService.ensure_commerce(
            merch,
            validated_data={
                'variants': [{'property_value': 'L', 'stock': 10}],
            },
        )
        ProductService.sync_merch_variants(product, 0, [])  # Удаляем всё

        assert not product.variants.get(property_value='L').is_active

        # Снова добавляем "L"
        ProductService.sync_merch_variants(
            product,
            0,
            [{'property_value': 'L', 'stock': 50}],
        )

        variant = product.variants.get(property_value='L')

        assert variant.is_active is True
        assert variant.stock == 50
        assert product.variants.filter(property_value='L').count() == 1
