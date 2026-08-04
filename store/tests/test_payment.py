"""Тесты сервиса интеграции с ЮKassa."""

from decimal import Decimal

import pytest

from store.exceptions import ReceiptValidationError
from store.models import Order, OrderItem
from store.services.payment import build_receipt_items


@pytest.fixture
def receipt_order_factory(user, variant_factory):
    """Создает заказ для тестирования фискального чека."""

    def create_order(
        *,
        total,
        unit_price,
        quantity,
        promocode_discount=Decimal('0.00'),
        delivery_price=Decimal('0.00'),
        delivery=None,
        product_info=None,
    ) -> Order:
        variant = variant_factory(
            'merch',
            price=unit_price,
        )

        order = Order.objects.create(
            user=user,
            full_name='Test User',
            email='test@example.com',
            phone='+79990000000',
            subtotal=unit_price * quantity,
            promocode_discount=promocode_discount,
            delivery_price=delivery_price,
            total=total,
            delivery=delivery,
        )

        OrderItem.objects.create(
            order=order,
            product_variant=variant,
            price_at_purchase=unit_price,
            unit_price=unit_price,
            quantity=quantity,
            promocode_discount=promocode_discount,
            product_info=product_info
            or {
                'kind': 'Мерч',
                'name': 'Футболка',
            },
        )

        return order

    return create_order


@pytest.mark.django_db
def test_build_receipt_items_with_even_price_distribution(
    receipt_order_factory,
):
    """Цена делится без остатка → создается одна позиция чека."""
    order = receipt_order_factory(
        total=Decimal('300.00'),
        unit_price=Decimal('100.00'),
        quantity=3,
    )

    receipt_items = build_receipt_items(order)

    assert receipt_items == [
        {
            'description': 'Мерч Футболка',
            'quantity': 3,
            'amount': {
                'value': '100.00',
                'currency': 'RUB',
            },
            'vat_code': 1,
            'payment_subject': 'commodity',
            'payment_mode': 'full_prepayment',
        },
    ]


@pytest.mark.django_db
def test_build_receipt_items_compensates_missing_kopeck(
    receipt_order_factory,
):
    """Не хватает копейки → остаток добавляется последней единице."""
    order = receipt_order_factory(
        total=Decimal('100.00'),
        unit_price=Decimal('33.34'),
        quantity=3,
        promocode_discount=Decimal('0.02'),
    )

    receipt_items = build_receipt_items(order)

    assert [
        (
            item['quantity'],
            item['amount']['value'],
        )
        for item in receipt_items
    ] == [
        (2, '33.33'),
        (1, '33.34'),
    ]


@pytest.mark.django_db
def test_build_receipt_items_compensates_extra_kopecks(
    receipt_order_factory,
):
    """Появляется избыток → разница вычитается из последней единицы."""
    order = receipt_order_factory(
        total=Decimal('100.00'),
        unit_price=Decimal('16.67'),
        quantity=6,
        promocode_discount=Decimal('0.02'),
    )

    receipt_items = build_receipt_items(order)

    assert [
        (
            item['quantity'],
            item['amount']['value'],
        )
        for item in receipt_items
    ] == [
        (5, '16.67'),
        (1, '16.65'),
    ]


@pytest.mark.django_db
def test_build_receipt_items_with_single_product(
    receipt_order_factory,
):
    """Одна единица товара → одна позиция без перераспределения цены."""
    order = receipt_order_factory(
        total=Decimal('100.00'),
        unit_price=Decimal('100.00'),
        quantity=1,
    )

    receipt_items = build_receipt_items(order)

    assert len(receipt_items) == 1

    assert receipt_items[0]['quantity'] == 1
    assert receipt_items[0]['amount']['value'] == '100.00'


@pytest.mark.django_db
def test_build_receipt_items_adds_delivery(
    receipt_order_factory,
    delivery_courier,
):
    """Стоимость доставки больше нуля → добавляется отдельной позицией."""
    order = receipt_order_factory(
        total=Decimal('1500.00'),
        unit_price=Decimal('1000.00'),
        quantity=1,
        delivery_price=Decimal('500.00'),
        delivery=delivery_courier,
    )

    receipt_items = build_receipt_items(order)

    assert len(receipt_items) == 2

    assert receipt_items[1] == {
        'description': 'СДЭК - курьером до двери',
        'quantity': 1,
        'amount': {
            'value': '500.00',
            'currency': 'RUB',
        },
        'vat_code': 1,
        'payment_subject': 'service',
        'payment_mode': 'full_prepayment',
    }


@pytest.mark.django_db
def test_build_receipt_items_raises_error_when_total_mismatches(
    receipt_order_factory,
):
    """Сумма чека не совпадает с заказом → ReceiptValidationError."""
    order = receipt_order_factory(
        total=Decimal('101.00'),
        unit_price=Decimal('100.00'),
        quantity=1,
    )

    with pytest.raises(
        ReceiptValidationError,
        match='Сумма позиций чека не совпадает с суммой заказа',
    ):
        build_receipt_items(order)
