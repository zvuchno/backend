import logging
from collections import defaultdict
from decimal import Decimal

import requests
from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import ValidationError

from store.constants import (
    CDEK_API_MAX_PAGES,
    CDEK_API_PAGE_SIZE,
    CITY_CACHE_TIMEOUT,
    DEFAULT_CACHE_TIMEOUT,
    MONEY_DISPLAY_PRECISION,
    ZERO_MONEY,
)
from store.exceptions import CDEKIntegrationError
from store.models import Product
from store.services.cart_service import CartCalculationService
from users.models import ArtistProfile

logger = logging.getLogger(__name__)


class CDEKService:
    """Сервис для взаимодействия с API СДЭК (v2).

    Класс инкапсулирует логику авторизации, расчетов и управления заказами.
    Использует кэширование данных в Redis (через Django Cache) для оптимизации
    количества запросов к API.

    Methods:
        get_access_token(): Получает или обновляет токен доступа OAuth2.
        get_city_code_by_name: Получает код города СДЭК по его названию.
        get_offices: Возвращает список пунктов выдачи для города.
        calculate: Рассчитывает стоимость доставки на основе корзины.
        create_order: Регистрирует накладную в СДЭК.

    """

    def __init__(self):
        """Инициализация параметров интеграции со СДЭК из настроек Django."""
        self.api_url = settings.CDEK_API_URL
        self.client_id = settings.CDEK_CLIENT_ID
        self.client_secret = settings.CDEK_CLIENT_SECRET
        self.tariff_code_office = settings.TARIFF_OFFICE
        self.tariff_code_door = settings.TARIFF_DOOR
        self.tariff_code_pickup = settings.TARIFF_PICKUP
        self.default_item_weight = settings.DEFAULT_ITEM_WEIGHT
        self.default_city = settings.DEFAULT_CITY

    def _auth_headers(self) -> dict[str, str]:
        """Формирование HTTP-заголовков авторизации со токеном Bearer."""
        return {
            'Authorization': f'Bearer {self.get_access_token()}',
            'Content-Type': 'application/json',
        }

    def get_access_token(self):
        """Получение токена СДЭК из памяти, кэша Django или через API."""
        cached_token = cache.get('cdek_access_token')
        if cached_token:
            self._token = cached_token
            logger.info('Получен токен CDEK из кеша.')
            return cached_token

        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        try:
            response = requests.post(
                f'{self.api_url}/oauth/token',
                data=data,
                timeout=10,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(
                'Ошибка авторизации СДЭК: '
                f'{getattr(e.response, "text", str(e))}',
            )
            raise ValidationError(f'Не удалось получить токен: {e}')

        token_data = response.json()
        new_token = token_data.get('access_token')
        expires_in = token_data.get('expires_in', 3600)

        cache.set('cdek_access_token', new_token, expires_in - 300)
        self._token = new_token
        logger.info('Получен токен от API CDEK.')
        return new_token

    def get_city_code_by_name(self, city_name_en):
        """Получает код города СДЭК по его названию."""
        url = f'{self.api_url}/location/cities'

        query = {'city': city_name_en}

        try:
            response = requests.get(
                url,
                headers=self._auth_headers(),
                params=query,
                timeout=10,
            )
            response.raise_for_status()
            cities_data = response.json()

            if cities_data:
                return cities_data[0].get('code')

            logger.warning(f'Город {city_name_en} не найден в базе СДЭК')
            return None

        except Exception as e:
            logger.error(f'Ошибка при поиске кода города: {str(e)}')
            return None

    def get_offices(self, params: dict) -> dict:
        """Оркестратор получения ПВЗ."""
        # Добавить параметр 'city' к запросу виджета на фронтенде!
        city = (
            str(
                params.get('city') or self.default_city,
            )
            .strip()
            .lower()
        )

        city_code = self._get_or_set_city_code(city)

        is_handout = params.get('is_handout')
        is_reception = params.get('is_reception')

        all_points = self._get_all_points_with_cache(
            city_code,
            city,
            is_handout,
            is_reception,
        )

        return self._paginate_points(all_points, params, city, city_code)

    def _get_or_set_city_code(self, city: str) -> str:
        """Логика получения и кэширования кода города."""
        cache_key = f'cdek:city_code:{city}'
        city_code = cache.get(cache_key)

        if city_code is None:
            logger.info(
                f'Код города "{city}" отсутствует в кэше. Запрашиваем у CDEK.',
            )
            city_code = self.get_city_code_by_name(city)
            if not city_code:
                raise ValidationError(f'Город "{city}" не найден.')

            cache.set(cache_key, city_code, timeout=CITY_CACHE_TIMEOUT)
            logger.info(f'Код города "{city}" ({city_code}) сохранён в кэш.')
        else:
            logger.info(f'Код города "{city}" получен из кэша: {city_code}')

        return city_code

    def _get_all_points_with_cache(
        self,
        city_code: str,
        city_name: str,
        is_handout,
        is_reception,
    ) -> list:
        """Логика кэширования списка ПВЗ."""
        cache_key = (
            f'cdek:points:city={city_code}:h={is_handout}:r={is_reception}'
        )
        all_points = cache.get(cache_key)

        if all_points is None:
            logger.info(
                f'Получение ПВЗ CDEK из API. city={city_name} ({city_code})',
            )
            all_points = self._fetch_all_points_from_api(
                city_code,
                is_handout,
                is_reception,
            )
            cache.set(cache_key, all_points, timeout=DEFAULT_CACHE_TIMEOUT)
            logger.info(
                f'Получено {len(all_points)} ПВЗ для города '
                f'{city_name} ({city_code})',
            )
        else:
            logger.info(
                f'Получено из кеша {len(all_points)} ПВЗ для города '
                f'{city_name} ({city_code})',
            )

        return all_points

    def _fetch_all_points_from_api(
        self,
        city_code: str,
        is_handout,
        is_reception,
    ) -> list:
        """Реализация цикла запроса к API с обработкой ошибок."""
        all_points = []
        page = 0
        api_params = {
            'lang': 'rus',
            'city_code': city_code,
            'size': CDEK_API_PAGE_SIZE,
        }
        if is_handout is not None:
            api_params['is_handout'] = is_handout
        if is_reception is not None:
            api_params['is_reception'] = is_reception

        while True:
            api_params['page'] = page
            try:
                response = requests.get(
                    f'{self.api_url}/deliverypoints',
                    headers=self._auth_headers(),
                    params=api_params,
                    timeout=10,
                )
                response.raise_for_status()
            except requests.RequestException as e:
                if e.response is not None:
                    logger.error(
                        'CDEK вернул ошибку при получении ПВЗ. '
                        'status=%s, params=%s, body=%s',
                        e.response.status_code,
                        api_params,
                        e.response.text,
                    )
                else:
                    logger.error(
                        'Ошибка соединения с API CDEK при получении ПВЗ. '
                        'params=%s',
                        api_params,
                    )
                raise CDEKIntegrationError() from e

            data = response.json()
            if not data:
                break
            all_points.extend(data)

            total_pages = int(response.headers.get('X-Total-Pages', page + 1))
            page += 1
            if page >= total_pages or page >= CDEK_API_MAX_PAGES:
                break

        return all_points

    def _paginate_points(
        self,
        all_points: list,
        params: dict,
        city: str,
        city_code: str,
    ) -> dict:
        """Логика пагинации с полным логированием ответа."""
        try:
            page = max(0, int(params.get('page', 0)))
            size = min(max(1, int(params.get('size', 100))), 500)
        except (TypeError, ValueError):
            page = 0
            size = 100

        start = page * size
        end = start + size

        total_elements = len(all_points)
        returned_points = all_points[start:end]

        logger.info(
            'Ответ CDEK Widget API сформирован. '
            f'city={city} ({city_code}), '
            f'page={page}, size={size}, '
            f'total_elements={total_elements}, '
            f'returned_points={len(returned_points)}',
        )

        return {
            'points': returned_points,
            'page': page,
            'size': size,
            'total_elements': total_elements,
            'total_pages': (total_elements + size - 1) // size,
        }

    def calculate(
        self,
        city: str,
        cart,
        delivery_type: str = 'office',
    ) -> dict:
        """Расчет стоимости доставки СДЭК на основе содержимого корзины."""
        if not cart:
            raise ValidationError({'detail': 'Ваша корзина пуста.'})

        calculation_service = CartCalculationService(cart)

        # Получаем список ID уникальных артистов, чей мерч в корзине
        cart_artist_ids = calculation_service.get_merch_artist_ids()

        if not cart_artist_ids:  # Если мерча нет
            logger.warning('Нет физических товаров для доставки.')
            raise ValidationError({
                'detail': 'Нет физических товаров для доставки.',
            })

        # Создаем словарь {artist_id: city_code} - в один запрос
        artist_city_code = dict(
            ArtistProfile.objects.filter(id__in=cart_artist_ids).values_list(
                'id',
                'shipping_point__city_code',
            ),
        )
        # Считаем количество мерча для каждого артиста
        artist_quantities = defaultdict(int)
        cart_items = cart.items.filter(
            product_variant__product__product_type=Product.ProductType.MERCH,
        ).select_related(
            'product_variant__product__merch__owner__artist_profile',
        )

        for item in cart_items:
            owner = item.product_variant.product.merch.owner
            artist_profile = getattr(owner, 'artist_profile', None)

            if artist_profile:
                artist_id = artist_profile.id
                if artist_id in artist_city_code:
                    artist_quantities[artist_id] += item.quantity

        total_delivery_sum = ZERO_MONEY

        # Списки для сбора сроков доставки от разных артистов
        all_min_periods = []
        all_max_periods = []

        # Проходим по сгруппированным артистам и суммируем доставки
        for artist_id, items_count in artist_quantities.items():
            from_location_code = artist_city_code.get(artist_id)

            if not from_location_code:
                raise ValidationError({
                    'detail': f'У артиста id={artist_id} не указан код '
                    'населенного пункта для отгрузки товара.',
                })

            delivery_data = self._calculate_for_artist(
                from_location=from_location_code,
                to_location=city,
                items_count=items_count,
                delivery_type=delivery_type,
            )

            total_delivery_sum += delivery_data['total_sum']

            if delivery_data['period_min'] is not None:
                all_min_periods.append(delivery_data['period_min'])
            if delivery_data['period_max'] is not None:
                all_max_periods.append(delivery_data['period_max'])

            logger.info(
                f'Корзина {cart.user}: рассчитана сумма доставки '
                f'от артиста ID: {artist_id}, from_location: '
                f'{from_location_code}, to_location: {city}, items_count '
                f'= {items_count} -> {delivery_data["total_sum"]} руб.',
            )

        delivery_sum = round(total_delivery_sum, MONEY_DISPLAY_PRECISION)

        # Вычисляем финальные сроки (берем худший максимум из всех плеч)
        period_min = max(all_min_periods) if all_min_periods else None
        period_max = max(all_max_periods) if all_max_periods else None

        logger.info(
            f'Корзина {cart.user}, тип доставки: {delivery_type}, '
            f'итоговая сумма доставки всех товаров -> {delivery_sum} руб. '
            f'Сроки: {period_min}-{period_max} дн.',
        )

        return {
            'delivery_sum': delivery_sum,
            'period_min': period_min,
            'period_max': period_max,
        }

    def _calculate_for_artist(
        self,
        to_location: str,
        from_location: str,
        items_count: int,
        delivery_type: str,
    ) -> dict:
        """Метод для расчета доставки в API СДЭК по конкретным артистам."""
        if delivery_type == 'office':
            tariff_code = self.tariff_code_office
        elif delivery_type == 'door':
            tariff_code = self.tariff_code_door
        elif delivery_type == 'pickup':
            tariff_code = self.tariff_code_pickup
        else:
            raise ValidationError({
                'detail': f'Неподдерживаемый тип тарифа: {delivery_type}.',
            })

        # Умножаем базовый вес на количество мерчей этого артиста
        total_weight = items_count * int(self.default_item_weight)

        payload = {
            'tariff_code': tariff_code,
            'from_location': {'code': int(from_location)},
            'to_location': {'code': int(to_location)},
            'packages': [
                {
                    'weight': int(total_weight),
                },
            ],
        }

        url = f'{self.api_url}/calculator/tariff'
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._auth_headers(),
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()

            return {
                'total_sum': Decimal(str(data['total_sum'])),
                'period_min': data.get('period_min'),
                'period_max': data.get('period_max'),
            }

        except requests.RequestException as e:
            if e.response is not None:
                logger.error(
                    'CDEK вернул ошибку при расчёте доставки. '
                    'status=%s, payload=%s, body=%s',
                    e.response.status_code,
                    payload,
                    e.response.text,
                )
            raise CDEKIntegrationError(
                'Не удалось рассчитать стоимость доставки. '
                'Служба СДЭК временно недоступна, '
                'пожалуйста, попробуйте позже.',
            ) from e

    def suggest_cities(self, query):
        """Поиск доступных городов через саджест-API СДЭК."""
        url = f'{self.api_url}/location/suggest/cities'

        try:
            response = requests.get(
                url,
                headers=self._auth_headers(),
                params={'name': query, 'country_code': 'RU'},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            if e.response is not None:
                logger.error(
                    'CDEK вернул ошибку при поиске городов. '
                    'status=%s, query=%s, body=%s',
                    e.response.status_code,
                    query,
                    e.response.text,
                )
            else:
                logger.error(
                    'Ошибка соединения с API CDEK при поиске городов. '
                    'query=%s',
                    query,
                )

            raise CDEKIntegrationError(
                'Не удалось получить список городов. '
                'Служба СДЭК временно недоступна, '
                'пожалуйста, попробуйте позже.',
            ) from e
