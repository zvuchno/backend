"""Тесты логики создания заказа."""

import pytest
from rest_framework import status

from store.models import CartItem, Order, OrderItem
from users.models import ConsentDocument, UserConsent


@pytest.mark.django_db
class TestCheckoutAPI:
    """Набор тестов для проверки оформления заказа."""

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        api_client,
        auth_client,
        checkout_url,
        cart_with_items,
        delivery_courier,
        consent_doc_pdn,
    ) -> None:
        """Автоматически прокидывает зависимости в self перед каждым тестом."""
        self.auth_client = auth_client
        self.api_client = api_client
        self.checkout_url = checkout_url
        self.cart_with_items = cart_with_items
        self.delivery = delivery_courier
        self.document = consent_doc_pdn

    def get_payload(self, **kwargs):
        """Генератор данных для чекаута."""
        payload = {
            'full_name': 'Звучно Тестер',
            'email': 'test@test.ru',
            'phone': '+79991112233',
            'personal_data_consent': True,
            'delivery': self.delivery.id,
            'city': 'Москва',
            'street': 'Ленина',
            'house': '1',
        }
        payload.update(kwargs)
        return payload

    # ========================== TESTS ==========================

    def test_create_order_success(self, user):
        """Авторизованный пользователь + корзина → успешный заказ и очистка."""
        response = self.auth_client.post(
            self.checkout_url,
            data=self.get_payload(),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Order.objects.count() == 1
        assert UserConsent.objects.filter(user=user).exists()
        assert self.cart_with_items.items.count() == 0

    def test_anon_checkout_flow(
        self,
        cart_url,
        cart_add_url,
        artist_user,
        variant_factory,
        consent_doc_newsletter,
    ):
        """Сквозной тест оформления заказа.

        Аноним → сессия + успешный заказ + очистка корзины + согласия.
        """
        response = self.api_client.get(cart_url)
        variant = variant_factory(product_type='merch', owner=artist_user)
        types = [
            ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
            ConsentDocument.DocumentType.LISTENER_NEWSLETTER,
        ]
        payload = {
            'product_variant': variant.id,
            'quantity': 2,
            'is_artist_subscription': 'true',
        }
        response = self.api_client.post(cart_add_url, payload, format='json')

        response = self.api_client.post(
            self.checkout_url,
            self.get_payload(),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Order.objects.count() == 1

        cart_response = self.api_client.get(cart_url)
        assert len(cart_response.data['items']) == 0
        assert (
            UserConsent.objects.filter(
                user__isnull=True,
                document__document_type__in=types,
            ).count()
            == 2
        )

    def test_checkout_integrity_snapshots(self):
        """Смена цены товара → в заказе сохраняется цена на момент покупки."""
        item = self.cart_with_items.items.first()
        initial_price = item.unit_price
        variant = item.product_variant

        response = self.auth_client.post(
            self.checkout_url,
            data=self.get_payload(),
            format='json',
        )

        variant.product.price += 1000
        variant.product.save()

        order_item = OrderItem.objects.get(
            order_id=response.data['id'],
            product_variant=variant,
        )
        assert order_item.unit_price == initial_price

    def test_checkout_atomic_rollback_on_error(self, monkeypatch):
        """Ошибка при сохранении → откат транзакции, корзина не удаляется."""
        payload = self.get_payload()

        # Функция кидаеющая исключение
        def mock_bulk_create_crash(*args, **kwargs) -> None:
            raise Exception('Force Database Crash')

        # Подменяем  метод bulk_create у менеджера OrderItem
        monkeypatch.setattr(
            OrderItem.objects,
            'bulk_create',
            mock_bulk_create_crash,
        )

        response = self.auth_client.post(self.checkout_url, data=payload)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert Order.objects.count() == 0
        assert self.cart_with_items.items.count() > 0

    def test_checkout_empty_cart_fails(self):
        """Пустая корзина → 400 Bad Request."""
        self.cart_with_items.items.all().delete()

        response = self.auth_client.post(
            self.checkout_url,
            data=self.get_payload(),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Корзина пуста' in response.data['cart'][0]
        assert Order.objects.count() == 0

    def test_checkout_requires_consent(self):
        """Нет согласия (personal_data_consent=False) → ValidationError."""
        payload = self.get_payload(personal_data_consent=False)

        response = self.auth_client.post(
            self.checkout_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert 'personal_data_consent' in response.data
        assert response.data['personal_data_consent'][0].code in ([
            'invalid',
            'required',
        ])
        assert Order.objects.count() == 0

    def test_checkout_merch_requires_address(self, delivery_courier):
        """Заказ с мерчем без адреса → 400 Bad Request."""
        # Payload с курьерской доставкой, но пустым адресом
        payload = self.get_payload(
            delivery=delivery_courier.id,
            city='Москва',
            street='',
            house='',
        )

        response = self.auth_client.post(
            self.checkout_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert all(field in response.data for field in ['street', 'house'])
        assert Order.objects.count() == 0

    def test_checkout_digital_album_no_address_success(self, variant_factory):
        """Заказ только с цифровым товаром → успех без адреса."""
        self.cart_with_items.items.all().delete()
        variant = variant_factory('track')
        self.cart_with_items.items.create(product_variant=variant, quantity=1)

        payload = self.get_payload()
        payload.pop('city', None)
        payload.pop('street', None)
        payload.pop('house', None)
        response = self.auth_client.post(
            self.checkout_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Order.objects.count() == 1
        order = Order.objects.get(id=response.data['id'])
        assert order.street == ''

    def test_checkout_fails_with_inactive_document(self):
        """Неактивный документ согласия → 400 Bad Request."""
        # Деактивируем текущий активный документ
        self.document.is_active = False
        self.document.save()

        response = self.auth_client.post(
            self.checkout_url,
            data=self.get_payload(),
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in response.data
        assert 'Нет активного документа' in response.data['detail'][0]
        assert Order.objects.count() == 0

    def test_checkout_fails_with_inactive_delivery(self, inactive_delivery):
        """Выбор неактивного способа доставки → 400 Bad Request."""
        payload = self.get_payload(delivery=inactive_delivery.id)

        response = self.auth_client.post(
            self.checkout_url,
            data=payload,
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'delivery' in response.data
        assert response.data['delivery'][0].code in ['does_not_exist']

    def test_checkout_consent_linking(self, user):
        """Чекаут → корректная привязка UserConsent к заказу и документу."""
        pyload = self.get_payload()
        response = self.auth_client.post(
            self.checkout_url,
            data=pyload,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        order = Order.objects.get(id=response.data['id'])

        assert order.consents.exists()
        consent = order.consents.first()
        assert consent.order == order
        assert consent.email == pyload['email']
        assert consent.document == self.document

    def test_checkout_delivery_methods_only_for_merch(self, variant_factory):
        """Список доставок → только при наличии мерча в корзине."""
        self.cart_with_items.items.all().delete()
        variant_digt = variant_factory('track')
        variant_merch = variant_factory('merch')

        self.cart_with_items.items.create(product_variant=variant_digt)

        response = self.auth_client.get(self.checkout_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['deliveries'] == []

        self.cart_with_items.items.create(product_variant=variant_merch)

        response = self.auth_client.get(self.checkout_url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['deliveries']) > 0

    def test_artist_subscription_consent_created(
        self,
        user,
        artist_user,
        variant_factory,
        consent_doc_newsletter,
    ):
        """Заказ с подпиской на рассылку → создано корректное согласие."""
        variant = variant_factory(owner=artist_user)
        CartItem.objects.create(
            cart=self.cart_with_items,
            product_variant=variant,
            quantity=1,
            is_artist_subscription=True,
        )

        response = self.auth_client.post(
            self.checkout_url,
            self.get_payload(),
        )

        assert response.status_code == status.HTTP_201_CREATED

        order = Order.objects.first()
        consent = UserConsent.objects.get(
            document__document_type=ConsentDocument.DocumentType.LISTENER_NEWSLETTER,
        )
        assert consent.order == order
        assert consent.artist == artist_user.artist_profile
        assert consent.email == self.get_payload()['email']
