import logging

import requests
from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import ValidationError

from store.constants import (
    CDEK_API_MAX_PAGES,
    CDEK_API_PAGE_SIZE,
    CITY_CACHE_TIMEOUT,
    DEFAULT_CACHE_TIMEOUT,
)
from store.exceptions import CDEKIntegrationError

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

    """

    def __init__(self):
        """Инициализация параметров интеграции со СДЭК из настроек Django."""
        self.api_url = settings.CDEK_API_URL
        self.client_id = settings.CDEK_CLIENT_ID
        self.client_secret = settings.CDEK_CLIENT_SECRET
        self.tariff_code_pickpoint = settings.TARIFF_PICKPOINT
        self.tariff_code_courier = settings.TARIFF_COURIER
        self.default_item_weight = settings.DEFAULT_ITEM_WEIGHT

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
        city = str(params.get('city', '')).strip().lower()
        if not city:
            raise ValidationError('Параметр city обязателен.')

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
            except requests.RequestException:
                logger.exception('Ошибка API CDEK')
                raise CDEKIntegrationError()

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
