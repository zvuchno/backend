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
        # Для локальной разработки
        if ip_address in ['127.0.0.1', 'localhost', '::1']:
            return self._get_default_city()

        # Проверяем кэш
        cache_key = f'geo_ip_{ip_address}'
        cached = cache.get(cache_key)
        if cached:
            logger.info(f'Кешированная локация: {cached.get("city")}')
            return cached

        # Определяем город через выбранного провайдера
        if self.provider == 'ip_api':
            result = self._get_city_from_ip_api(ip_address)
        else:
            result = self._get_default_city()

        # Кэшируем на сутки
        cache.set(cache_key, result, 86400)
        return result

    def _get_city_from_ip_api(self, ip_address) -> dict:
        """Бесплатный сервис ip-api.com (50 запросов/мин)."""
        try:
            response = requests.get(
                f'http://ip-api.com/json/{ip_address}',
                timeout=2,
            )
            data = response.json()

            if data.get('status') == 'success':
                logger.info(f'Получена локация ip-api: {data.get("city")}')
                return {
                    'city': data.get('city'),
                    'region': data.get('regionName'),
                    'country': data.get('countryCode'),
                    'latitude': data.get('lat'),
                    'longitude': data.get('lon'),
                    'source': 'ip-api',
                }
        except Exception as e:
            logger.error(f'Ошибка ip-api: {e}')

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
