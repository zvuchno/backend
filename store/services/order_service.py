"""Модуль бизнес-логики создания заказов.

Инкапсулирует сервисы транзакционного создания заказов со снапшотами данных.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from store.constants import ZERO_MONEY
from store.models import Delivery, Order, OrderItem
from store.serializers import DeliverySerializer
from users.models import ConsentDocument, UserConsent


class OrderService:
    """Сервис для управления жизненным циклом заказов.

    Отвечает за подготовку данных для оформления заказа (checkout),
    создание записей заказов и позиций,
    фиксацию юридически значимых действий (согласия).
    """

    @staticmethod
    def checkout_info(user, cart) -> dict:
        """Сервис формирования данных для оформления заказа.

        Собирает:
        - дефолтные данные пользователя для предзаполнения формы
        - итоговую стоимость корзины
        - доступные способы доставки (если в корзине есть мерч)
        """
        cart = cart or (user.cart if user else None)

        has_merch = cart.items.filter(
            product_variant__product__product_type='merch',
        ).exists()

        deliveries_qs = Delivery.objects.none()
        if has_merch:
            deliveries_qs = Delivery.objects.filter(is_active=True)

        profile = getattr(user, 'listener_profile', None)

        return {
            'user_defaults': {
                'full_name': getattr(profile, 'full_name', '') or '',
                'email': user.email if user else '',
                'phone': str(getattr(user, 'phone', '') or ''),
            },
            'subtotal': cart.subtotal,
            'deliveries': DeliverySerializer(deliveries_qs, many=True).data,
        }

    @staticmethod
    @transaction.atomic
    def create_order(
        user,
        cart,
        validated_data,
        ip_address=None,
        user_agent=None,
    ) -> Order:
        """Транзакционный процесс преобразования корзины в оформленный заказ.

        Выполняет следующие шаги:
        1. Блокирует позиции корзины для предотвращения race condition.
        2. Рассчитывает финальную стоимость - total.
        3. Создает объект Order и OrderItem (со снапшотами данных о товарах).
        4. Регистрирует согласие пользователя на обработку ПДн (UserConsent).
        5. Очищает корзину (удаляет позиции или объект целиком для анонимов).
        """
        cart_items = cart.items.select_for_update().select_related(
            'product_variant__product',
        )

        if not cart_items.exists():
            raise ValidationError('Нельзя оформить заказ с пустой корзиной.')

        personal_data_consent = validated_data.pop(
            'personal_data_consent',
            None,
        )
        delivery = validated_data.pop('delivery', None)
        delivery_price = ZERO_MONEY
        delivery_name = ''

        if delivery:
            delivery_price = delivery.price
            delivery_name = delivery.name

        subtotal = cart.subtotal
        total = cart.total + delivery_price

        # Создаем заказ
        order = Order.objects.create(
            user=user if user and user.is_authenticated else None,
            status=Order.Status.CREATED,
            subtotal=subtotal,
            delivery_price=delivery_price,
            total=total,
            delivery=delivery_name,
            **validated_data,  # full_name, email, phone, адресные поля
        )

        # Формируем позиции заказа
        order_items = []
        for item in cart_items:
            variant = item.product_variant
            product = variant.product

            # Собираем JSON-снапшот
            product_info_snapshot = {
                'name': variant.variant_name,
                'product_type': product.product_type,
                'property_name': product.property_name,
                'property_value': variant.property_value,
                'sku': variant.sku,
            }

            order_items.append(
                OrderItem(
                    order=order,
                    product_variant=variant,
                    comment=item.comment or '',
                    price_at_purchase=product.price,
                    unit_price=item.unit_price,
                    quantity=item.quantity,
                    # TODO: Добавить promocode_discount
                    product_info=product_info_snapshot,
                ),
            )

        OrderItem.objects.bulk_create(order_items)

        # Получаем текущий активный документ
        consent_document = ConsentDocument.objects.filter(
            document_type=ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
            is_active=True,
        ).first()

        # Фиксируем согласие пользователя
        if personal_data_consent:
            if not consent_document:
                raise ValidationError(
                    'Нет активного документа согласия для слушателя.',
                )
            UserConsent.objects.create(
                email=(
                    user.email
                    if user and user.is_authenticated
                    else validated_data.get('email')
                ),
                user=user if user and user.is_authenticated else None,
                order=order,
                document=consent_document,
                ip_address=ip_address,
                user_agent=user_agent,
                accepted_at=timezone.now(),
            )

        # Очищаем корзину
        cart_items.delete()

        # Дропаем сессионную
        if not user or not user.is_authenticated:
            cart.delete()

        return order
