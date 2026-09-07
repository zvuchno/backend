from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework.exceptions import ValidationError

from store.models import Cart, CartItem
from store.services.cdek import CDEKService

pytestmark = pytest.mark.django_db


@pytest.fixture
def cdek_service():
    """Экземпляр CDEKService для тестов."""
    return CDEKService()


class TestCDEKServiceCalculateParallel:
    """Тесты параллельного расчёта доставки СДЭК по артистам."""

    def test_calculate_aggregates_costs_from_multiple_artists(
        self,
        cdek_service,
        user_factory,
        artist_user,
        other_artist_user,
        variant_factory,
    ):
        """Мерч от двух артистов → сумма и сроки доставки агрегируются."""
        buyer = user_factory(email='buyer@test.com', username='buyer')
        cart = Cart.objects.create(user=buyer)

        merch_1 = variant_factory('merch', artist=artist_user.artist_profile)
        merch_2 = variant_factory(
            'merch',
            artist=other_artist_user.artist_profile,
        )

        CartItem.objects.create(cart=cart, product_variant=merch_1, quantity=2)
        CartItem.objects.create(cart=cart, product_variant=merch_2, quantity=1)

        responses_by_from_location = {
            '44': {
                'total_sum': Decimal('300.00'),
                'period_min': 2,
                'period_max': 4,
            },
            '137': {
                'total_sum': Decimal('450.50'),
                'period_min': 3,
                'period_max': 5,
            },
        }

        def fake_calculate_for_artist(
            from_location: str,
            to_location: str,
            items_count: int,
            tariffs: str,
        ) -> dict:
            return responses_by_from_location[from_location]

        with patch.object(
            cdek_service,
            '_calculate_for_artist',
            side_effect=fake_calculate_for_artist,
        ) as mocked:
            result = cdek_service.calculate(city_code='270', cart=cart)

        assert mocked.call_count == 2
        assert result['delivery_sum'] == Decimal('750.50')
        assert result['period_min'] == 3
        assert result['period_max'] == 5
        assert set(result['delivery_calculation'].keys()) == {
            str(artist_user.artist_profile.id),
            str(other_artist_user.artist_profile.id),
        }

    def test_calculate_propagates_error_from_one_artist(
        self,
        cdek_service,
        user_factory,
        artist_user,
        other_artist_user,
        variant_factory,
    ):
        """Ошибка СДЭК одного из артистов → ValidationError пробрасывается."""
        buyer = user_factory(email='buyer2@test.com', username='buyer2')
        cart = Cart.objects.create(user=buyer)

        merch_1 = variant_factory('merch', artist=artist_user.artist_profile)
        merch_2 = variant_factory(
            'merch',
            artist=other_artist_user.artist_profile,
        )

        CartItem.objects.create(cart=cart, product_variant=merch_1, quantity=1)
        CartItem.objects.create(cart=cart, product_variant=merch_2, quantity=1)

        def fake_calculate_for_artist(
            from_location: str,
            to_location: str,
            items_count: int,
            tariffs: str,
        ) -> dict:
            if from_location == '137':
                raise ValidationError({'detail': 'CDEK недоступен.'})
            return {
                'total_sum': Decimal('100.00'),
                'period_min': 1,
                'period_max': 2,
            }

        with patch.object(
            cdek_service,
            '_calculate_for_artist',
            side_effect=fake_calculate_for_artist,
        ):
            with pytest.raises(ValidationError):
                cdek_service.calculate(city_code='270', cart=cart)

    def test_calculate_raises_when_artist_has_no_shipping_city(
        self,
        cdek_service,
        user_factory,
        artist_without_shipping_point,
        variant_factory,
    ):
        """Не указан ПВЗ отправления → ValidationError до похода в СДЭК."""
        buyer = user_factory(email='buyer3@test.com', username='buyer3')
        cart = Cart.objects.create(user=buyer)

        merch = variant_factory(
            'merch',
            artist=artist_without_shipping_point.artist_profile,
        )
        CartItem.objects.create(cart=cart, product_variant=merch, quantity=1)

        with patch.object(cdek_service, '_calculate_for_artist') as mocked:
            with pytest.raises(ValidationError):
                cdek_service.calculate(city_code='270', cart=cart)

        mocked.assert_not_called()

    def test_calculate_empty_cart_raises_validation_error(
        self,
        cdek_service,
        user_factory,
    ):
        """Пустая корзина → ValidationError без обращения к артистам."""
        buyer = user_factory(email='buyer4@test.com', username='buyer4')
        cart = Cart.objects.create(user=buyer)

        with pytest.raises(ValidationError):
            cdek_service.calculate(city_code='270', cart=cart)

    def test_calculate_no_merch_in_cart_raises_validation_error(
        self,
        cdek_service,
        user_factory,
        artist_user,
        variant_factory,
    ):
        """В корзине только цифра → ValidationError, а не нулевая доставка."""
        buyer = user_factory(email='buyer5@test.com', username='buyer5')
        cart = Cart.objects.create(user=buyer)

        album = variant_factory('album', artist=artist_user.artist_profile)
        CartItem.objects.create(cart=cart, product_variant=album, quantity=1)

        with patch.object(cdek_service, '_calculate_for_artist') as mocked:
            with pytest.raises(ValidationError):
                cdek_service.calculate(city_code='270', cart=cart)

        mocked.assert_not_called()
