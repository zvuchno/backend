import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class LocationService:
    """Сервис для геоданных: определение города по IP."""

    def __init__(self):
        """Провайдеры."""
        self.provider = getattr(settings, 'GEO_PROVIDER', 'ip_api')

    def get_city_by_ip(self, ip_address):
        """Определение города по IP-адресу.

        Returns:
            dict: {
                'city': 'Новосибирск',
                'region': 'Новосибирская область',
                'country': 'RU',
                'latitude': 55.0415,
                'longitude': 82.9346
            }

        """
        logger.debug(f'Запрос геоданных для IP: "{ip_address}"')

        # Для локальной разработки
        if not ip_address or ip_address in ['127.0.0.1', 'localhost', '::1']:
            logger.info(
                'Используется дефолтный город для локального/пустого IP: '
                f'{ip_address}',
            )
            return self._get_default_city()

        # Проверяем кэш
        cache_key = f'geo_ip_{ip_address}'
        cached = cache.get(cache_key)
        if cached and cached.get('city'):
            logger.info(
                f'Кешированная локация для {ip_address}: {cached.get("city")}',
            )
            return cached

        # Определяем город через выбранного провайдера
        if self.provider == 'ip_api':
            result = self._get_city_from_ip_api(ip_address)
        else:
            result = self._get_default_city()

        # Кэшируем на сутки
        if result and result.get('city'):
            cache.set(cache_key, result, 86400)
        else:
            logger.warning(
                f'Город для IP {ip_address} не определен. '
                'Результат НЕ закэширован.',
            )

        return result

    def _get_city_from_ip_api(self, ip_address) -> dict:
        """Бесплатный сервис ip-api.com (50 запросов/мин)."""
        try:
            response = requests.get(
                f'http://ip-api.com/json/{ip_address}',
                timeout=2,
            )
            if response.status_code != 200:
                logger.error(
                    f'ip-api вернул HTTP {response.status_code} '
                    f'для IP {ip_address}. Текст: {response.text}',
                )
                return self._get_default_city()
            data = response.json()

            if (
                data.get('status') == 'success'
                and data.get('city')
                and data.get('countryCode') == 'RU'
            ):
                logger.info(f'Получена локация ip-api: {data.get("city")}')
                return {
                    'city': data.get('city'),
                    'region': data.get('regionName'),
                    'country': data.get('countryCode'),
                    'latitude': data.get('lat'),
                    'longitude': data.get('lon'),
                    'source': 'ip-api',
                }
            reason = data.get(
                'message',
                'Причина неизвестна (возможно, пустой город или не Россия)',
            )
            logger.warning(
                f'ip-api не подошел для IP {ip_address}. '
                f'Статус: {data.get("status")}, Страна: '
                f'{data.get("countryCode")}. Причина: {reason}',
            )

        except Exception as e:
            logger.error(
                f'Ошибка при запросе к ip-api для IP {ip_address}: {e}',
                exc_info=True,
            )

        return self._get_default_city()

    def _get_default_city(self) -> dict:
        """Город по умолчанию."""
        return {
            'city': settings.DEFAULT_CITY
            if hasattr(settings, 'DEFAULT_CITY')
            else 'Москва',
            'region': None,
            'country': 'RU',
            'latitude': None,
            'longitude': None,
            'source': 'default',
        }
