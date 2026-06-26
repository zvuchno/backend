import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class LocationService:
    """Сервис для геоданных: определение города по IP."""

    def __init__(self):
        """Провайдеры."""
        # Ожидаем одно из значений: 'ip_api' или 'dadata'
        self.provider = getattr(settings, 'GEO_PROVIDER', 'dadata')

    def get_city_by_ip(self, ip_address):
        """Определение города по IP-адресу.

        Returns:
            dict: {
                'city': 'Новосибирск',
                'region': 'Новосибирская область',
                'country': 'RU',
            }

        """
        logger.debug('Запрос геоданных для IP: %s', ip_address)

        # Для локальной разработки
        if not ip_address or ip_address in ['127.0.0.1', 'localhost', '::1']:
            logger.info(
                'Используется дефолтный город для локального/пустого IP: %s',
                ip_address,
            )
            return self._get_default_city()

        # Проверяем кэш
        cache_key = f'geo_ip_{ip_address}'
        cached = cache.get(cache_key)
        if cached and cached.get('city'):
            logger.info(
                'Кешированная локация для IP: %s city=%s',
                ip_address,
                cached.get('city'),
            )
            return cached

        # Определяем город через выбранного провайдера
        if self.provider == 'dadata':
            result = self._get_city_from_dadata(ip_address)
        elif self.provider == 'ip_api':
            result = self._get_city_from_ip_api(ip_address)
        else:
            logger.error(
                'Неизвестный GEO_PROVIDER: %s',
                self.provider,
            )
            result = self._get_default_city()

        # Кэшируем на сутки
        if result and result.get('city'):
            cache.set(cache_key, result, 86400)
        else:
            logger.warning(
                'Город не определен для IP: %s provider=%s',
                ip_address,
                self.provider,
            )

        return result

    def _get_city_from_dadata(self, ip_address) -> dict:
        """Сервис DaData (iplocate)."""
        api_key = getattr(settings, 'DADATA_API_KEY', None)

        if not api_key:
            logger.error('DADATA_API_KEY не задан в settings')
            return self._get_default_city()

        try:
            response = requests.post(
                'https://suggestions.dadata.ru/suggestions/api/4_1/rs/iplocate/address',
                json={'ip': ip_address},
                headers={
                    'Authorization': f'Token {api_key}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                timeout=2,
            )

            if response.status_code != 200:
                logger.warning(
                    'DaData HTTP error status=%s body=%s ip=%s',
                    response.status_code,
                    response.text,
                    ip_address,
                )
                return self._get_default_city()

            payload = response.json()

            location = payload.get('location')
            if not location:
                logger.info(
                    'DaData: location пустой для IP: %s payload=%s',
                    ip_address,
                    payload,
                )
                return self._get_default_city()

            data = location.get('data') or {}

            if data.get('country_iso_code') != 'RU':
                logger.info(
                    'DaData: не RU IP  ip=%s country=%s',
                    ip_address,
                    data.get('country_iso_code'),
                )
                return self._get_default_city()

            city = data.get('city')
            if not city:
                logger.info(
                    'DaData: город не найден для IP: %s',
                    ip_address,
                )
                return self._get_default_city()

            result = {
                'city': city,
                'region': data.get('region_with_type'),
                'country': data.get('country_iso_code'),
            }

            logger.info(
                'DaData: определён город=%s ip=%s',
                city,
                ip_address,
            )

            return result

        except Exception as e:
            logger.error(
                'Ошибка DaData для IP=%s error=%s',
                ip_address,
                e,
                exc_info=True,
            )
            return self._get_default_city()

    def _get_city_from_ip_api(self, ip_address) -> dict:
        """Бесплатный сервис ip-api.com (50 запросов/мин)."""
        try:
            response = requests.get(
                f'http://ip-api.com/json/{ip_address}',
                timeout=2,
            )

            if response.status_code != 200:
                logger.error(
                    'ip-api HTTP error status=%s ip=%s body=%s',
                    response.status_code,
                    ip_address,
                    response.text,
                )
                return self._get_default_city()

            data = response.json()

            if data.get('status') != 'success':
                logger.warning(
                    'ip-api не определил город ip=%s status=%s message=%s',
                    ip_address,
                    data.get('status'),
                    data.get('message'),
                )
                return self._get_default_city()

            if not data.get('city') or data.get('countryCode') != 'RU':
                logger.warning(
                    'ip-api неверный результат ip=%s city=%s country=%s',
                    ip_address,
                    data.get('city'),
                    data.get('countryCode'),
                )
                return self._get_default_city()

            logger.info(
                'ip-api получена локация=%s ip=%s',
                data.get('city'),
                ip_address,
            )

            return {
                'city': data.get('city'),
                'region': data.get('regionName'),
                'country': data.get('countryCode'),
            }

        except Exception as e:
            logger.error(
                'ip-api ошибка при запросе ip=%s error=%s',
                ip_address,
                e,
                exc_info=True,
            )
            return self._get_default_city()

    def _get_default_city(self) -> dict:
        """Город по умолчанию."""
        return {
            'city': getattr(settings, 'DEFAULT_CITY', 'Москва'),
            'region': None,
            'country': 'RU',
        }
