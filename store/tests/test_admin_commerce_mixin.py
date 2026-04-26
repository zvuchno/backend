"""Интеграционный тест CommerceBaseMixin."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from store.models import Merch, MerchKind, Product

User = get_user_model()


class MerchAdminTest(TestCase):
    """Интеграционный тест CommerceBaseMixin в Django Admin.

    Проверяется, что миксин корректно обрабатывает сохранение объекта
    через админку и формирует данные для бизнес-слоя.

    Основная цель тестов:
    - убедиться, что save_related собирает данные из formsets
    - гарантировать корректную передачу данных в ProductService.ensure_commerce
    - проверить, что через админку создаются связанные сущности
    (Product, ProductVariant) согласно бизнес-логике сервиса.
    """

    def setUp(self):
        """Создаёт суперпользователя и авторизованный client."""
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='password',
            email='a@a.com',
        )
        self.client = Client()
        self.client.force_login(self.admin_user)

        self.add_url = reverse('admin:store_merch_add')

    def _get_merch_payload(self, name, kind_id, price, variants) -> dict:
        """Формирует POST payload для Django Admin формы."""
        data = {
            'name': name,
            'kind': str(kind_id),
            'visibility': 'public',
            'allow_overpay': 'on',
            '_save': 'Save',
            # --- Image inline ---
            'images_merch-TOTAL_FORMS': '0',
            'images_merch-INITIAL_FORMS': '0',
            # --- Product inline ---
            'product-TOTAL_FORMS': '1',
            'product-INITIAL_FORMS': '0',
            'product-0-price': price,
            # --- Variants inline ---
            'product-0-variants-TOTAL_FORMS': str(len(variants)),
            'product-0-variants-INITIAL_FORMS': '0',
            'product-empty-variants-TOTAL_FORMS': '0',
            'product-empty-variants-INITIAL_FORMS': '0',
        }

        for i, v in enumerate(variants):
            data[f'product-0-variants-{i}-property_value'] = v['value']
            data[f'product-0-variants-{i}-stock'] = v['stock']

        return data

    def test_merch_admin_creates_product_with_variants(self):
        """Проверяет полный цикл создания Merch через Django Admin.

        Ожидается:
        - создаётся Merch
        - создаётся Product
        - создаются ровно N ProductVariant
        - значения variants соответствуют входным данным
        """
        kind = MerchKind.objects.create(name='Одежда', slug='clothing')
        merch_name = 'T-shirt'
        price = Decimal('2500')

        variants_data = [
            {'value': 'XL', 'stock': '10'},
            {'value': 'S', 'stock': '5'},
        ]

        payload = self._get_merch_payload(
            name=merch_name,
            kind_id=kind.id,
            price=str(price),
            variants=variants_data,
        )

        response = self.client.post(self.add_url, data=payload, follow=True)

        assert response.status_code == 200
        merch = Merch.objects.get(name='T-shirt')
        assert merch is not None

        product = Product.objects.get(merch=merch)
        assert product.price == Decimal('2500')

        variants = product.variants.all()
        actual = {v.property_value: v.stock for v in variants}
        expected = {'XL': 10, 'S': 5}
        assert actual == expected
