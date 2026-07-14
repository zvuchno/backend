"""Модуль бизнес-логики создания заказов.

Инкапсулирует сервисы транзакционного создания заказов со снапшотами данных.
"""

import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from .cart_calculation_service import CartCalculationService
from store.constants import ZERO_MONEY
from store.models import Delivery, Order, OrderItem
from store.services import CDEKService
from users.models import ConsentDocument, UserConsent

logger = logging.getLogger(__name__)


class OrderService:
    """Сервис для управления жизненным циклом заказов.

    Отвечает за подготовку данных для оформления заказа (checkout),
    создание записей заказов и позиций,
    фиксацию юридически значимых действий (согласия).
    """

    @staticmethod
    def checkout_info(user, cart, city, city_code) -> dict:
        """Сервис формирования данных для оформления заказа.

        Собирает:
        - дефолтные данные пользователя для предзаполнения формы
        - итоговую стоимость корзины (с учётом промокодов)
        - доступные способы доставки (если в корзине есть мерч)
        """
        cart = cart or (user.cart if user else None)
        calculation_service = CartCalculationService(cart)

        # Получаем список ID уникальных артистов, чей мерч в корзине
        cart_artist_ids = calculation_service.get_merch_artist_ids()

        if not cart_artist_ids:  # Мерч тут есть?
            deliveries_qs = Delivery.objects.none()
            pickup_points_data = []
        else:
            deliveries_qs = Delivery.objects.filter(is_active=True)
            pickup_points_data = (
                calculation_service.get_available_pickup_points()
            )

            # Если для текущей корзины нет доступных точек — скрываем самовывоз
            if not pickup_points_data.exists():
                deliveries_qs = deliveries_qs.exclude(
                    delivery_type=Delivery.DeliveryType.ARTIST_PICKUP,
                )

        profile = getattr(user, 'listener_profile', None)

        return {
            'user_defaults': {
                'full_name': getattr(profile, 'full_name', '') or '',
                'email': user.email if user else '',
                'phone': str(getattr(user, 'phone', '') or ''),
                'city': city,
                'city_code': city_code,
            },
            'subtotal': calculation_service.get_total(),
            'deliveries': deliveries_qs,
            'pickup_points': pickup_points_data,
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
        logger.info(
            'Начало оформления заказа: user_id=%s, cart_id=%s',
            user.id if user else None,
            cart.id,
        )
        # Блокируем строки корзины
        cart_items = (
            cart.items
            .select_for_update()
            .select_related('product_variant__product')
            .prefetch_related(
                'product_variant__product__album__owner__artist_profile',
                'product_variant__product__track__album__owner__artist_profile',
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
                logger.warning(
                    'Попытка оформить заказ с неактивным промокодом: '
                    'promocode_id=%s, cart_id=%s',
                    cart.promocode_id,
                    cart.id,
                )
                raise ValidationError(
                    'Применённый промокод больше не активен.',
                )

            # Обновляем инстанс в корзине
            cart.promocode = promocode

        calc_service = CartCalculationService(cart)
        item_discounts = calc_service.get_item_discounts()

        if cart.promocode and calc_service.get_discount_total() == ZERO_MONEY:
            logger.warning(
                'Промокод не применим к товарам в корзине: '
                'promocode_id=%s, cart_id=%s',
                cart.promocode_id,
                cart.id,
            )
            raise ValidationError(
                'Этот промокод невозможно применить к товарам в корзине.',
            )

        personal_data_consent = validated_data.pop(
            'personal_data_consent',
            None,
        )
        delivery = validated_data.pop('delivery', None)
        tariffs = validated_data.pop('tariffs', None)
        pickup_point = validated_data.pop('pickup_point', None)
        cdek_city_code = validated_data.get('cdek_city_code')

        pickup_point_data = {}
        if pickup_point:
            pickup_point_data = {
                'address': pickup_point.address,
                'date': pickup_point.pickup_date.isoformat(),
            }

        subtotal = calc_service.get_subtotal()
        promocode_discount = calc_service.get_discount_total()
        delivery_price, delivery_calculation = (
            OrderService._get_delivery_result(
                cart,
                delivery,
                cdek_city_code,
                tariffs,
            )
        )
        total = calc_service.get_total() + delivery_price

        # Создаем заказ с фиксацией промокода и его общей скидки
        order = Order.objects.create(
            user=user if user and user.is_authenticated else None,
            status=Order.Status.CREATED,
            subtotal=subtotal,
            promocode=cart.promocode,
            promocode_discount=promocode_discount,
            delivery_calculation=delivery_calculation,
            delivery_price=delivery_price,
            total=total,
            delivery=delivery,
            pickup_point=pickup_point_data,
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
        logger.info(
            'Заказ создан: order_id=%s, user_id=%s, total=%s',
            order.id,
            user.id if user else None,
            total,
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
                logger.info(
                    'Подписка на артиста добавлена: order_id=%s, artist_id=%s',
                    order.id,
                    artist_profile.id,
                )

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
                logger.error(
                    'Нет активного документа согласия на рассылку '
                    '(LISTENER_NEWSLETTER). '
                    'order будет отменён: order_id=%s',
                    order.id,
                )
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
                logger.error(
                    'Нет активного документа согласия на обработку ПДн '
                    '(LISTENER_PERSONAL_DATA). '
                    'order будет отменён: order_id=%s',
                    order.id,
                )
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
    def _get_delivery_result(
        cart,
        delivery,
        cdek_city_code,
        tariffs,
    ) -> tuple[Decimal, dict]:
        """Возвращает (delivery_price, delivery_calculation) для заказа.

        Расчёт выполняется только если выбрана доставка СДЭК (курьер/ПВЗ)
        и в корзине есть мерч — иначе оба поля пустые.
        """
        if not delivery or delivery.delivery_type not in (
            Delivery.DeliveryType.COURIER,
            Delivery.DeliveryType.PICKPOINT,
        ):
            return ZERO_MONEY, {}

        if not CartCalculationService(cart).get_merch_artist_ids():
            return ZERO_MONEY, {}

        result = CDEKService().calculate(
            city_code=cdek_city_code,
            cart=cart,
            tariffs=tariffs,
        )

        delivery_sum = result.get('delivery_sum')
        if delivery_sum is None:
            logger.error(
                'CDEK вернул ответ без delivery_sum: '
                'cart_id=%s, city_code=%s, result=%s',
                cart.id,
                cdek_city_code,
                result,
            )
            raise ValidationError('Не удалось рассчитать стоимость доставки.')
        return Decimal(delivery_sum), result.get('delivery_calculation', {})

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
            logger.info(
                'Промокод применен: promocode_id=%s, order_id=%s',
                order.promocode_id,
                order.id,
            )
