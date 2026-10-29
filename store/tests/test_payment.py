"""Тесты сервиса интеграции с ЮKassa."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from store.exceptions import ReceiptValidationError
from store.models import Order, OrderItem, Payment, ProductVariant
from store.services.payment import build_receipt_items, mark_payment_succeeded
from store.tests.factories import MerchKindFactory


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
            artist=variant.product.artist,
            payout_recipient=variant.product.payout_recipient,
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


@pytest.fixture
def reserved_payment_factory(user):
    """Создаёт зарезервированный заказ и ожидающий платёж."""

    def create_order(*variants) -> tuple[Order, Payment]:
        total = sum(
            (variant.product.price for variant in variants),
            Decimal('0.00'),
        )
        order = Order.objects.create(
            user=user,
            status=Order.Status.RESERVED,
            full_name='Test User',
            email='test@example.com',
            phone='+79990000000',
            subtotal=total,
            total=total,
        )

        for variant in variants:
            product = variant.product
            OrderItem.objects.create(
                order=order,
                product_variant=variant,
                artist=product.artist,
                payout_recipient=product.payout_recipient,
                price_at_purchase=product.price,
                unit_price=product.price,
                quantity=1,
                product_info={'name': product.name},
            )

        payment = Payment.objects.create(
            order=order,
            amount=total,
        )
        return order, payment

    return create_order


@pytest.fixture
def payment_callback_mocks():
    """Не допускает внешних вызовов из post-commit callbacks оплаты."""
    with (
        patch(
            'store.services.payment.AlbumArchiveScheduler.schedule_by_id',
        ) as archive_mock,
        patch(
            'store.services.payment.notify_artists_about_new_order_task.delay',
        ) as notify_mock,
        patch(
            'store.services.payment.register_cdek_orders_task.delay',
        ) as cdek_mock,
    ):
        yield archive_mock, notify_mock, cdek_mock


@pytest.mark.django_db
def test_successful_album_payment_schedules_archive_after_commit(
    variant_factory,
    reserved_payment_factory,
    payment_callback_mocks,
    django_capture_on_commit_callbacks,
):
    """Цифровой альбом планирует ZIP перед остальными callbacks."""
    variant = variant_factory('album')
    order, payment = reserved_payment_factory(variant)
    archive_mock, notify_mock, cdek_mock = payment_callback_mocks
    callback_order = []
    archive_mock.side_effect = lambda album_id: callback_order.append(
        ('archive', album_id),
    )
    notify_mock.side_effect = lambda order_id: callback_order.append(
        ('notify', order_id),
    )
    cdek_mock.side_effect = lambda order_id: callback_order.append(
        ('cdek', order_id),
    )

    with django_capture_on_commit_callbacks(execute=True):
        mark_payment_succeeded(payment)
        archive_mock.assert_not_called()

    assert callback_order == [
        ('archive', variant.product.album_id),
        ('notify', order.pk),
        ('cdek', order.pk),
    ]


@pytest.mark.django_db
def test_successful_album_carrier_payment_schedules_archive(
    variant_factory,
    reserved_payment_factory,
    payment_callback_mocks,
    django_capture_on_commit_callbacks,
):
    """Физический носитель альбома также планирует его ZIP."""
    album_variant = variant_factory('album')
    carrier_variant = variant_factory('merch')
    carrier = carrier_variant.product.merch
    carrier.album = album_variant.product.album
    carrier.kind = MerchKindFactory(is_carrier=True)
    carrier.save(update_fields=('album', 'kind'))
    _, payment = reserved_payment_factory(carrier_variant)
    archive_mock, _, _ = payment_callback_mocks

    with django_capture_on_commit_callbacks(execute=True):
        mark_payment_succeeded(payment)

    archive_mock.assert_called_once_with(album_variant.product.album_id)


@pytest.mark.django_db
def test_successful_merch_and_track_payment_skips_archive(
    variant_factory,
    reserved_payment_factory,
    payment_callback_mocks,
    django_capture_on_commit_callbacks,
):
    """Трек, обычный мерч и носитель без альбома не планируют ZIP."""
    track_variant = variant_factory('track')
    merch_variant = variant_factory('merch')
    merch = merch_variant.product.merch
    merch.album = track_variant.product.track.release
    merch.kind = MerchKindFactory(is_carrier=False)
    merch.save(update_fields=('album', 'kind'))
    orphan_carrier_variant = variant_factory('merch')
    orphan_carrier = orphan_carrier_variant.product.merch
    orphan_carrier.kind = MerchKindFactory(is_carrier=True)
    orphan_carrier.save(update_fields=('kind',))
    _, payment = reserved_payment_factory(
        track_variant,
        merch_variant,
        orphan_carrier_variant,
    )
    archive_mock, _, _ = payment_callback_mocks

    with django_capture_on_commit_callbacks(execute=True):
        mark_payment_succeeded(payment)

    archive_mock.assert_not_called()


@pytest.mark.django_db
def test_successful_payment_schedules_album_once_for_multiple_items(
    variant_factory,
    reserved_payment_factory,
    payment_callback_mocks,
    django_capture_on_commit_callbacks,
):
    """Несколько позиций одного альбома дают один вызов scheduler."""
    first_variant = variant_factory('album')
    second_variant = ProductVariant.objects.create(
        product=first_variant.product,
        stock=None,
        property_value='second',
    )
    _, payment = reserved_payment_factory(first_variant, second_variant)
    archive_mock, _, _ = payment_callback_mocks

    with django_capture_on_commit_callbacks(execute=True):
        mark_payment_succeeded(payment)

    archive_mock.assert_called_once_with(first_variant.product.album_id)


@pytest.mark.django_db
def test_repeated_successful_payment_does_not_reschedule_archive(
    variant_factory,
    reserved_payment_factory,
    payment_callback_mocks,
    django_capture_on_commit_callbacks,
):
    """Повторный платёж и уже оплаченный заказ не создают callbacks."""
    variant = variant_factory('album')
    _, payment = reserved_payment_factory(variant)
    archive_mock, notify_mock, cdek_mock = payment_callback_mocks

    with django_capture_on_commit_callbacks(execute=True):
        mark_payment_succeeded(payment)

    archive_mock.reset_mock()
    notify_mock.reset_mock()
    cdek_mock.reset_mock()

    with django_capture_on_commit_callbacks(execute=True):
        mark_payment_succeeded(payment)

    archive_mock.assert_not_called()
    notify_mock.assert_not_called()
    cdek_mock.assert_not_called()

    second_payment = Payment.objects.create(
        order=payment.order,
        amount=payment.amount,
    )

    with django_capture_on_commit_callbacks(execute=True):
        mark_payment_succeeded(second_payment)

    second_payment.refresh_from_db()
    assert second_payment.status == Payment.PaymentStatus.SUCCEEDED
    archive_mock.assert_not_called()
    notify_mock.assert_not_called()
    cdek_mock.assert_not_called()


@pytest.mark.django_db
def test_archive_callback_failure_keeps_order_paid(
    variant_factory,
    reserved_payment_factory,
    payment_callback_mocks,
    django_capture_on_commit_callbacks,
):
    """Ошибка scheduler после commit не портит оплату и уведомления."""
    variant = variant_factory('album')
    order, payment = reserved_payment_factory(variant)
    archive_mock, notify_mock, cdek_mock = payment_callback_mocks
    archive_mock.side_effect = RuntimeError('archive broker failed')

    with django_capture_on_commit_callbacks(execute=True):
        mark_payment_succeeded(payment)

    order.refresh_from_db()
    payment.refresh_from_db()

    assert order.status == Order.Status.PAID
    assert payment.status == Payment.PaymentStatus.SUCCEEDED
    notify_mock.assert_called_once_with(order.pk)
    cdek_mock.assert_called_once_with(order.pk)


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
