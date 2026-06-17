"""Тесты корзины покупок."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response

from store.models import Cart, CartItem


class TestCartAPI:
    """Набор тестов для проверки функциональности корзины покупок."""

    def _login_user(self, api_client, login_url, user) -> Response:
        """Вспомогательный метод для авторизации."""
        return api_client.post(
            login_url,
            data={'email': user.email, 'password': user.raw_password},
            format='json',
        )

    def test_add_item_to_cart(
        self,
        auth_client,
        cart_add_url,
        variant_factory,
        user,
    ):
        """Проверяет добавление записи в корзину через POST."""
        variant = variant_factory(product_type='merch')

        payload = {
            'product_variant': variant.id,
            'quantity': 2,
        }

        response = auth_client.post(cart_add_url, data=payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED

        item = CartItem.objects.get(
            cart__user=user,
            product_variant=variant,
        )
        assert item.quantity == 2
        assert response.data['items'][0]['quantity'] == 2

    def test_update_cart_item_with_patch(
        self,
        auth_client,
        cart_url,
        variant_factory,
        user,
    ):
        """Проверяет частичное обновление корзины через PATCH."""
        variant = variant_factory(product_type='merch')

        cart = Cart.objects.get_or_create(user=user)[0]
        CartItem.objects.create(
            cart=cart,
            product_variant=variant,
            quantity=1,
        )
        payload = {
            'items': [
                {
                    'product_variant': variant.id,
                    'quantity': 10,
                    'price_with_donation': Decimal('3000.00'),
                    'comment': 'Thank you!',
                },
            ],
        }
        response = auth_client.patch(cart_url, data=payload, format='json')
        assert response.status_code == status.HTTP_200_OK

        item = CartItem.objects.get(cart=cart, product_variant=variant)
        assert item.quantity == 10
        assert item.price_with_donation == Decimal('3000.00')
        assert item.comment == 'Thank you!'

    def test_sync_cart_with_put(
        self,
        auth_client,
        cart_url,
        variant_factory,
        user,
    ):
        """Проверяет полную синхронизацию корзины через PUT."""
        album = variant_factory(product_type='album')
        merch = variant_factory(product_type='merch')
        cart = Cart.objects.get_or_create(user=user)[0]
        CartItem.objects.create(
            cart=cart,
            product_variant=merch,
            quantity=3,
        )
        CartItem.objects.create(
            cart=cart,
            product_variant=album,
            quantity=1,
        )

        assert CartItem.objects.filter(cart=cart).count() == 2

        payload = {
            'items': [
                {
                    'product_variant': merch.id,
                    'quantity': 5,
                },
            ],
        }
        response = auth_client.put(cart_url, data=payload, format='json')

        assert response.status_code == status.HTTP_200_OK

        assert CartItem.objects.filter(cart=cart).count() == 1
        item = CartItem.objects.get(cart=cart, product_variant=merch)
        assert item.product_variant.id == merch.id
        assert item.quantity == 5

    def test_remove_item_from_cart(
        self,
        auth_client,
        variant_factory,
        user,
    ):
        """Проверяет удаление позиции из корзины."""
        album = variant_factory(product_type='album')
        merch = variant_factory(product_type='merch')
        cart = Cart.objects.get_or_create(user=user)[0]
        items = [
            {'product_variant': album, 'quantity': 1},
            {'product_variant': merch, 'quantity': 3},
        ]
        for item in items:
            CartItem.objects.create(
                cart=cart,
                product_variant_id=item['product_variant'].id,
                quantity=item['quantity'],
            )

        assert CartItem.objects.filter(cart=cart).count() == 2

        url = reverse(
            'api:store:cart-remove-item',
            kwargs={'variant_id': merch.id},
        )
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not CartItem.objects.filter(
            cart__user=user,
            product_variant=merch,
        ).exists()
        assert CartItem.objects.filter(
            cart__user=user,
            product_variant=album,
        ).exists()

    # fmt: off
    @pytest.mark.parametrize('p_type, stock, req_qty, expected_status', [
        ('merch', 10, 5,  status.HTTP_201_CREATED),  # Мерч: в пределах стока
        ('merch', 10, 11, status.HTTP_400_BAD_REQUEST),  # Мерч: превышение
        ('merch', 10, -1, status.HTTP_400_BAD_REQUEST),  # Мерч: отрицательное
        ('album', None, 1, status.HTTP_201_CREATED),  # Альбом: 1 шт - ОК
        ('album', None, 2, status.HTTP_400_BAD_REQUEST),  # Альбом: больше 1
        ('track', None, 1, status.HTTP_201_CREATED),  # Трек: 1 шт - ОК
        ('track', None, 2, status.HTTP_400_BAD_REQUEST),  # Трек: больше 1
    ])
    # fmt: on
    def test_add_to_cart_constraints(
        self,
        api_client,
        cart_add_url,
        variant_factory,
        p_type,
        stock,
        req_qty,
        expected_status,
    ):
        """Проверка лимитов количества в зависимости от типа продукта."""
        variant = variant_factory(product_type=p_type, stock=stock)
        response = api_client.post(
            cart_add_url,
            data={
                'product_variant': variant.id,
                'quantity': req_qty,
            },
            format='json',
        )
        assert response.status_code == expected_status

    def test_anonymous_cart_merges_on_login(
        self,
        api_client,
        variant_factory,
        login_url,
        cart_add_url,
        user,
    ):
        """Проверяет слияние анонимной корзины с корзиной пользователя."""
        variant = variant_factory(product_type='merch')
        payload = {
            'product_variant': variant.id,
            'quantity': 2,
            'comment': 'Test guest comment',
            'is_artist_subscription': 'true',
        }
        # Делаем запрос, чтобы создалась сессия и корзина
        response = api_client.post(cart_add_url, data=payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        # Проверяем, что в базе есть анонимная корзина
        assert Cart.objects.filter(user__isnull=True).count() == 1

        login_response = self._login_user(api_client, login_url, user)
        assert login_response.status_code == status.HTTP_200_OK
        # Анонимная корзина удалена после мержа
        assert Cart.objects.filter(user__isnull=True).count() == 0
        # У юзера должна появиться корзина
        user_cart = Cart.objects.get(user=user)
        assert user_cart.items.filter(
            product_variant=variant,
            quantity=2,
            is_artist_subscription=True,
        ).exists()
        item = user_cart.items.get(product_variant=variant)
        assert item.comment == 'Test guest comment'

    def test_merge_cart_with_duplicate_items(
        self,
        api_client,
        variant_factory,
        login_url,
        cart_add_url,
        user,
    ):
        """Проверка: при слиянии количество одинаковых товаров суммируется."""
        variant = variant_factory(product_type='merch')
        user_cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=user_cart,
            product_variant=variant,
            quantity=1,
        )
        payload = {'product_variant': variant.id, 'quantity': 2}
        api_client.post(cart_add_url, data=payload, format='json')

        assert user_cart.items.count() == 1
        assert user_cart.items.first().quantity == 1

        anon_cart = Cart.objects.get(user__isnull=True)
        assert anon_cart.items.count() == 1
        assert anon_cart.items.first().quantity == 2

        self._login_user(api_client, login_url, user)
        user_cart.refresh_from_db()
        assert user_cart.items.count() == 1
        assert user_cart.items.first().quantity == 3

    def test_merge_carts_respects_stock_limit(
        self,
        api_client,
        variant_factory,
        login_url,
        cart_add_url,
        user,
    ):
        """Проверка: при мерже количество ограничивается остатком на складе."""
        variant = variant_factory(product_type='merch', stock=5)
        # У юзера в корзине уже лежат 4 штуки
        user_cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=user_cart,
            product_variant=variant,
            quantity=4,
        )
        # Аноним докидывает еще 3 штуки (итого 7, но на складе 5)
        api_client.post(
            cart_add_url,
            data={'product_variant': variant.id, 'quantity': 3},
        )
        # Логинимся
        self._login_user(api_client, login_url, user)
        # Проверяем: количество 5 (максимум склада)
        user_item = CartItem.objects.get(
            cart__user=user,
            product_variant=variant,
        )
        assert user_item.quantity == 5

    def test_merge_carts_digital_product_limit(
        self,
        api_client,
        variant_factory,
        login_url,
        cart_add_url,
        user,
    ):
        """Проверка: цифра после мержа всегда остается в кол-ве 1 шт."""
        variant = variant_factory(product_type='track')
        # Юзер уже имеет этот трек в корзине
        user_cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=user_cart,
            product_variant=variant,
            quantity=1,
        )
        # Аноним добавляет тот же трек
        api_client.post(
            cart_add_url,
            data={'product_variant': variant.id, 'quantity': 1},
        )
        # Логинимся
        self._login_user(api_client, login_url, user)
        # Проверяем: количество по-прежнему 1
        user_item = CartItem.objects.get(
            cart__user=user,
            product_variant=variant,
        )
        assert user_item.quantity == 1

    def test_add_to_cart_respects_stock_limit(
        self,
        api_client,
        cart_add_url,
        variant_factory,
    ):
        """Проверка: добавление товара не может превысить остаток на складе."""
        stock_limit = 5
        # Создаем мерч с лимитом 5 штук
        variant = variant_factory(product_type='merch', stock=stock_limit)
        # Добавляем 3 штуки
        api_client.post(
            cart_add_url,
            data={'product_variant': variant.id, 'quantity': 3},
        )
        # Добавляем еще 4 (итого 7, но склад 5)
        response = api_client.post(
            cart_add_url,
            data={'product_variant': variant.id, 'quantity': 4},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'quantity' in response.data
        assert f'Доступно {stock_limit} шт.' in str(response.data['quantity'])

    def test_cart_price_with_donation_calculations(
        self,
        api_client,
        cart_add_url,
        cart_url,
        variant_factory,
    ):
        """Проверка: донат учитывается в расчетах.

        Донат корреткно отражается на price_with_donation,
        line_total и total корзины.
        """
        base_price = Decimal('1000.00')
        price_with_donation = Decimal('1500.00')
        quantity = 2
        variant = variant_factory(product_type='merch', price=base_price)

        payload = {
            'product_variant': variant.id,
            'quantity': quantity,
            'price_with_donation': price_with_donation,
            'is_artist_subscription': 'true',
        }

        response = api_client.post(cart_add_url, data=payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED

        item_data = response.data['items'][0]
        # Сумма строки: 1500 * 2 = 3000
        expected_line_total = price_with_donation * quantity
        assert Decimal(item_data['line_total']) == expected_line_total
        # Сумма корзины (subtotal)
        # Добавим еще один обычный товар без доната для чистоты эксперимента
        other_variant = variant_factory(
            product_type='album',
            price=Decimal('500.00'),
        )
        api_client.post(
            cart_add_url,
            data={
                'product_variant': other_variant.id,
                'quantity': 1,
                'is_artist_subscription': 'true',
            },
            format='json',
        )
        final_response = api_client.get(cart_url)
        # subtotal: 3000 (первый товар) + 500 (второй товар) = 3500
        assert Decimal(final_response.data['subtotal']) == (
            expected_line_total + Decimal('500.00')
        )
