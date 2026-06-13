"""Модуль бизнес-логики создания заказов.

Инкапсулирует сервисы транзакционного создания заказов со снапшотами данных.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from .cart_calculation_service import CartCalculationService
from store.constants import ZERO_MONEY
from store.models import Delivery, Order, OrderItem, Product
from users.models import ArtistPickupPoint, ConsentDocument, UserConsent


class OrderService:
    """Сервис для управления жизненным циклом заказов.

    Отвечает за подготовку данных для оформления заказа (checkout),
    создание записей заказов и позиций,
    фиксацию юридически значимых действий (согласия).
    """

    @staticmethod
    def checkout_info(user, cart, city) -> dict:
        """Сервис формирования данных для оформления заказа.

        Собирает:
        - дефолтные данные пользователя для предзаполнения формы
        - итоговую стоимость корзины (с учётом промокодов)
        - доступные способы доставки (если в корзине есть мерч)
        """
        cart = cart or (user.cart if user else None)
        calculation_service = CartCalculationService(cart)

        has_merch = cart.items.filter(
            product_variant__product__product_type=Product.ProductType.MERCH,
        ).exists()

        deliveries_qs = Delivery.objects.none()
        pickup_points = ArtistPickupPoint.objects.none()
        if has_merch:
            deliveries_qs = Delivery.objects.filter(is_active=True)
            pickup_points = ArtistPickupPoint.objects.filter(is_active=True)

        profile = getattr(user, 'listener_profile', None)

        return {
            'user_defaults': {
                'full_name': getattr(profile, 'full_name', '') or '',
                'email': user.email if user else '',
                'phone': str(getattr(user, 'phone', '') or ''),
                'city': city,
            },
            'subtotal': calculation_service.get_total(),
            'deliveries': deliveries_qs,
            'pickup_points': pickup_points,
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
        2. Инициализирует CartCalculationService для точного расчёта скидок.
        3. Создает объект Order и OrderItem (со снапшотами данных и скидок).
        4. Регистрирует согласие пользователя на рассылку и обработку ПДн.
        5. Очищает корзину (удаляет позиции или объект целиком для анонимов).
        """
        # Блокируем строки корзины
        cart_items = (
            cart.items
            .select_for_update()
            .select_related('product_variant__product')
            .prefetch_related(
                'product_variant__product__album__owner__artist_profile',
                'product_variant__product__track__owner__artist_profile',
                'product_variant__product__merch__owner__artist_profile',
            )
        )

        if not cart_items.exists():
            raise ValidationError('Нельзя оформить заказ с пустой корзиной.')

        if cart.promocode_id:
            # Блокируем запись промокода в БД до конца транзакции
            promocode = (
                cart.promocode.__class__.objects
                .select_for_update()
                .filter(id=cart.promocode_id)
                .first()
            )

            # Проверяем актуальный статус из базы данных
            if not promocode or not promocode.is_available:
                raise ValidationError(
                    'Применённый промокод больше не активен.',
                )

            # Обновляем инстанс в корзине
            cart.promocode = promocode

        calc_service = CartCalculationService(cart)
        item_discounts = calc_service.get_item_discounts()

        if cart.promocode and calc_service.get_discount_total() == ZERO_MONEY:
            raise ValidationError(
                'Этот промокод невозможно применить к товарам в корзине.',
            )

        personal_data_consent = validated_data.pop(
            'personal_data_consent',
            None,
        )
        delivery = validated_data.pop('delivery', None)

        delivery_price = delivery.price if delivery else ZERO_MONEY
        delivery_name = delivery.name if delivery else ''

        subtotal = calc_service.get_subtotal()
        promocode_discount = calc_service.get_discount_total()
        total = calc_service.get_total() + delivery_price

        # Создаем заказ с фиксацией промокода и его общей скидки
        order = Order.objects.create(
            user=user if user and user.is_authenticated else None,
            status=Order.Status.CREATED,
            subtotal=subtotal,
            promocode=cart.promocode,
            promocode_discount=promocode_discount,
            delivery_price=delivery_price,
            total=total,
            delivery=delivery_name,
            **validated_data,  # full_name, email, phone, адресные поля
        )

        artists_to_subscribe = OrderService._create_order_items(
            order,
            cart_items,
            item_discounts,
            cart.promocode,
        )

        OrderService._process_user_consents(
            user,
            order,
            validated_data.get('email'),
            artists_to_subscribe,
            personal_data_consent,
            ip_address,
            user_agent,
        )

        OrderService._finalize_cart_and_promocode(
            user,
            cart,
            order,
            cart_items,
        )

        return order

    @staticmethod
    def _create_order_items(
        order,
        cart_items,
        item_discounts,
        promocode,
    ) -> set:
        """Создает позиции заказа и возвращает наборы артистов для подписки."""
        order_items = []
        artists_to_subscribe = set()
        promocode_code = promocode.code if promocode else ''

        for item in cart_items:
            variant = item.product_variant
            product = variant.product
            item_promocode_discount = item_discounts.get(item.id, ZERO_MONEY)

            owner = getattr(product, 'owner', None)
            artist_profile = (
                getattr(
                    owner,
                    'artist_profile',
                    None,
                )
                if owner
                else None
            )
            artist_name = getattr(artist_profile, 'name', '')

            # Собираем JSON-снапшот
            product_info_snapshot = {
                'name': variant.variant_name,
                'artist_name': artist_name,
                'product_type': product.product_type,
                'property_name': product.property_name,
                'property_value': variant.property_value,
                'allow_overpay': product.allow_overpay,
                'promocode': promocode_code,
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
                    promocode_discount=item_promocode_discount,
                    product_info=product_info_snapshot,
                ),
            )
            if item.is_artist_subscription and artist_profile:
                artists_to_subscribe.add(artist_profile)

        OrderItem.objects.bulk_create(order_items)
        return artists_to_subscribe

    @staticmethod
    def _process_user_consents(
        user,
        order,
        email,
        artists_to_subscribe,
        personal_data_consent,
        ip_address,
        user_agent,
    ) -> None:
        """Регистрирует юридические согласия пользователя."""
        authenticated_user = user if user and user.is_authenticated else None
        # Согласие на рассылку
        if artists_to_subscribe:
            newsletter_doc = ConsentDocument.objects.filter(
                document_type=ConsentDocument.DocumentType.LISTENER_NEWSLETTER,
                is_active=True,
            ).first()

            if not newsletter_doc:
                raise ValidationError(
                    'Нет активного документа согласия на рассылку.',
                )

            UserConsent.objects.bulk_create([
                UserConsent(
                    email=email,
                    user=authenticated_user,
                    order=order,
                    artist=artist,
                    document=newsletter_doc,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                for artist in artists_to_subscribe
            ])

        # Согласие на обработку ПДн
        if personal_data_consent:
            personal_doc = ConsentDocument.objects.filter(
                document_type=ConsentDocument.DocumentType.LISTENER_PERSONAL_DATA,
                is_active=True,
            ).first()

            if not personal_doc:
                raise ValidationError(
                    'Нет активного документа согласия для слушателя.',
                )

            UserConsent.objects.create(
                email=email,
                user=authenticated_user,
                order=order,
                document=personal_doc,
                ip_address=ip_address,
                user_agent=user_agent,
            )

    @staticmethod
    def _finalize_cart_and_promocode(user, cart, order, cart_items) -> None:
        """Очищает корзину, промокод, и инкрементирует счетчик."""
        cart_items.delete()

        if not user or not user.is_authenticated:
            cart.delete()
        else:
            cart.promocode = None
            cart.save()

        if order.promocode_id:
            order.promocode.__class__.objects.filter(
                id=order.promocode_id,
            ).update(used_count=F('used_count') + 1)
