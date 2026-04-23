"""Тесты логики коммерческой обвязки контента."""

from decimal import Decimal

import pytest

from store.constants import CHAR_PRESET_DIGITAL, CHAR_PRESET_SIMPLE
from store.models import Album, Merch, Product, ProductVariant
from store.services import ProductService
from store.views.mixins import ProductActionMixin


@pytest.mark.django_db
class TestProductService:
    """Набор тестов для сервиса коммерческой логики ProductService."""

    def test_ensure_commerce_creates_objects(self, user):
        """Проверяет создание Product и ProductVariant при создании контента.

        Даже если цена не указана, коммерческие объекты
        должны быть созданы с дефолтными значениями.
        """
        album = Album.objects.create(
            name='Test Album Without Price',
            owner=user,
        )
        # Проверяем, что изначально связей нет
        assert not hasattr(album, 'product')
        assert Product.objects.filter(album=album).count() == 0

        product = ProductService.ensure_commerce(album)

        assert isinstance(product, Product)
        assert product.album == album

        variant = product.variants.first()
        assert variant is not None
        assert isinstance(variant, ProductVariant)

        assert variant.property_value == CHAR_PRESET_DIGITAL
        assert variant.stock is None

    def test_ensure_commerce_idempotency(self, variant_factory):
        """Тест: сервис не создает дубликаты, если объекты уже есть."""
        variant = variant_factory(product_type='track')
        product_existing = variant.product
        track = product_existing.track

        product_returned = ProductService.ensure_commerce(track)

        # Должен вернуться тот же самый объект, новых в базе не появляется
        assert product_returned.pk == product_existing.pk
        assert Product.objects.filter(track=track).count() == 1
        assert product_returned.variants.count() == 1

    def test_sync_merch_simple(self, user):
        """Проверяет создание и обновление простого мерча (1 вариант)."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)
        product = ProductService.ensure_commerce(merch)

        # Вызываем синхронизацию для простого товара
        ProductService.sync_merch_variants(
            product,
            stock=50,
            variants_data=None,
        )

        variant = product.variants.get(is_active=True)
        assert variant.stock == 50
        assert variant.property_value == CHAR_PRESET_SIMPLE
        assert product.variants.count() == 1

    def test_sync_merch_with_options(self, variant_factory):
        """Проверяет создание нескольких вариантов на основе характеристик."""
        merch = variant_factory(product_type='merch')
        product = ProductService.ensure_commerce(merch)

        options = [
            {
                'property_value': 'S',
                'stock': 10,
            },
            {
                'property_value': 'L',
                'stock': 5,
            },
        ]

        ProductService.sync_merch_variants(
            product,
            stock=0,
            variants_data=options,
        )

        active_variants = product.variants.filter(is_active=True)
        assert active_variants.count() == 2

        variant_s = active_variants.filter(property_value='S').first()
        assert variant_s is not None
        assert variant_s.stock == 10

        variant_l = active_variants.filter(property_value='L').first()
        assert variant_l is not None
        assert variant_l.stock == 5

    def test_transition_from_complex_to_simple(self, user):
        """Тест: деактивация старых вариантов при переходе к простому мерчу."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)
        product = ProductService.ensure_commerce(merch)

        # Сначала делаем сложный товар
        options = [
            {
                'property_value': 'S',
                'stock': 10,
            },
            {
                'property_value': 'M',
                'stock': 20,
            },
        ]
        ProductService.sync_merch_variants(
            product,
            stock=0,
            variants_data=options,
        )
        assert product.variants.filter(is_active=True).count() == 2

        # Переводим в простой товар (options=None)
        ProductService.sync_merch_variants(
            product,
            stock=100,
            variants_data=None,
        )

        # Проверяем: активен только один, остальные выключены
        active_variants = product.variants.filter(is_active=True)
        assert active_variants.count() == 1
        assert active_variants.first().stock == 100
        assert product.variants.filter(is_active=False).count() == 2

    def test_update_existing_variant_by_id(self, variant_factory):
        """Тест: при передаче ID вариант обновляется, а не пересоздается."""
        merch = variant_factory(product_type='merch')
        product = ProductService.ensure_commerce(merch)

        # Создаем начальный вариант
        initial_options = [
            {
                'property_value': 'Синий',
                'stock': 5,
            },
        ]
        ProductService.sync_merch_variants(
            product,
            stock=0,
            variants_data=initial_options,
        )

        variant_id = product.variants.get(is_active=True).id

        # Обновляем тот же вариант по ID
        update_options = [
            {
                'id': variant_id,
                'property_value': 'Красный',
                'stock': 15,
            },
        ]
        ProductService.sync_merch_variants(
            product,
            stock=0,
            variants_data=update_options,
        )

        # Проверяем, что ID тот же, а данные новые
        updated_variant = product.variants.get(is_active=True)
        assert updated_variant.id == variant_id
        assert updated_variant.stock == 15
        assert updated_variant.property_value == 'Красный'

    def test_partial_sync_deactivates_omitted_variants(self, user):
        """Проверяет, что варианты, не переданные в списке, деактивируются."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)
        product = ProductService.ensure_commerce(merch)
        # Создаем два варианта
        ProductService.sync_merch_variants(
            product,
            stock=0,
            variants_data=[
                {'property_value': '1', 'stock': 1},
                {'property_value': '2', 'stock': 2},
            ],
        )
        assert product.variants.count() == 2

        # Присылаем только один
        ProductService.sync_merch_variants(
            product,
            stock=0,
            variants_data=[
                {'property_value': '3', 'stock': 3},
            ],
        )

        # Должно быть: 1 активный (новый) и 2 неактивных (старых)
        assert product.variants.filter(is_active=True).count() == 1
        assert product.variants.filter(is_active=False).count() == 2

    def test_mixin_updates_product_price_and_overpay(self, variant_factory):
        """Тест: проверяет, что миксин обновляет цену и флаг доплаты."""
        merch = variant_factory(product_type='merch')
        validated_data = {
            'price': 1700.00,
            'allow_overpay': True,
            'property_name': 'Size',
            'stock': 10,
            'variants': None,
        }

        mixin = ProductActionMixin()
        mixin._update_product_data(merch, validated_data)

        product = merch.product
        assert Decimal(product.price) == Decimal('1700.00')
        assert product.allow_overpay is True
        assert product.property_name == 'Size'

    def test_sync_complex_merch_partial_update(self, user):
        """Проверяет умное обновление.

        Существующие обновляются, новые создаются, пропавшие выключаются.
        """
        merch = Merch.objects.create(name='T-Shirt', owner=user)
        product = ProductService.ensure_commerce(merch)
        # Сначала создаем S и M
        old_data = [
            {
                'property_value': 'S',
                'stock': 10,
            },
            {
                'property_value': 'M',
                'stock': 20,
            },
        ]
        ProductService.sync_merch_variants(
            product,
            stock=0,
            variants_data=old_data,
        )
        variant_s = product.variants.get(
            property_value='S',
        )
        variant_m_id = product.variants.get(property_value='M').id

        # Присылаем обновление: S (с ID) и L (новый, без ID)
        new_data = [
            {
                'id': variant_s.id,
                'property_value': 'S',
                'stock': 5,
            },
            {
                'property_value': 'L',
                'stock': 15,
            },
        ]
        ProductService.sync_merch_variants(
            product,
            stock=0,
            variants_data=new_data,
        )

        assert product.variants.filter(is_active=True).count() == 2
        # S обновился
        variant_s.refresh_from_db()
        assert variant_s.stock == 5
        # M деактивировался
        assert not ProductVariant.objects.get(id=variant_m_id).is_active
        # L создался
        assert product.variants.filter(
            property_value='L',
            is_active=True,
        ).exists()

    def test_sync_duplicate_property_values(self, user):
        """Тест: при передаче дублей новые объекты не плодятся."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)
        product = ProductService.ensure_commerce(merch)

        options = [
            {'property_value': 'S', 'stock': 10},
            {'property_value': 'S', 'stock': 20},  # Дубликат значения
        ]
        ProductService.sync_merch_variants(
            product,
            stock=0,
            variants_data=options,
        )
        # Должен быть 1 активный вариант "S" с последним стоком
        assert product.variants.filter(is_active=True).count() == 1
        assert product.variants.get(property_value='S').stock == 20

    def test_rename_variant_via_id(self, variant_factory):
        merch = variant_factory(product_type='merch')
        product = merch.product

        # Берем ID, который уже создала фабрика
        existing_variant = product.variants.first()
        v_id = existing_variant.id

        # Обновляем его по ID
        ProductService.sync_merch_variants(
            product,
            0,
            [{'id': v_id, 'property_value': 'Old', 'stock': 1}],
        )

        # Переименовываем из 'Old' в 'New'
        ProductService.sync_merch_variants(
            product,
            0,
            [{'id': v_id, 'property_value': 'New', 'stock': 1}],
        )

        assert product.variants.count() == 1
        assert product.variants.get().property_value == 'New'
        assert product.variants.get().id == v_id

    def test_reactivate_deleted_variant(self, user):
        """Тест: старый вариант активируется при повторном добавлении."""
        merch = Merch.objects.create(name='T-Shirt', owner=user)
        product = ProductService.ensure_commerce(merch)

        ProductService.sync_merch_variants(
            product,
            0,
            [{'property_value': 'L', 'stock': 10}],
        )
        ProductService.sync_merch_variants(product, 0, [])  # Удаляем всё

        assert product.variants.get(property_value='L').is_active is False

        # Снова добавляем "L"
        ProductService.sync_merch_variants(
            product,
            0,
            [{'property_value': 'L', 'stock': 50}],
        )

        variant = product.variants.get(property_value='L')
        assert variant.is_active is True
        assert variant.stock == 50
        # Проверяем, что в базе не появилось второго объекта "L"
        assert product.variants.filter(property_value='L').count() == 1
