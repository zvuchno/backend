import ipaddress
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class LocationService:
    """Сервис для геоданных: определение ФИАС по IP."""

    def __init__(self):
        """Провайдеры."""
        # Ожидаем одно из значений: 'dadata'
        self.provider = getattr(settings, 'GEO_PROVIDER', 'dadata')

    def get_fias_by_ip(self, ip_address):
        """Определение ФИАС населенного пункта по IP-адресу.

        Returns:
            dict: {
                'city_fias_id': 'dd71e526-d850-46db-97db-164391414c5b',
            }

        """
        logger.debug('Запрос геоданных для IP: %s', ip_address)

        if not ip_address:
            logger.info('Пустой IP, используется ФИАС по умолчанию.')
            return self._get_default_fias()

        try:
            ip_obj = ipaddress.ip_address(ip_address)
        except ValueError:
            logger.info(
                'Невалидный IP: %s, используется ФИАС по умолчанию.',
                ip_address,
            )
            return self._get_default_fias()

        if ip_obj.is_loopback or ip_obj.is_private:
            logger.info(
                'Используется ФИАС по умолчанию для '
                'локального/приватного IP: %s',
                ip_address,
            )
            return self._get_default_fias()

        # Проверяем кэш
        cache_key = f'geo_ip_{ip_address}'
        cached = cache.get(cache_key)
        if cached and cached.get('city_fias_id'):
            logger.info(
                'Кешированная локация для IP: %s city_fias_id=%s',
                ip_address,
                cached['city_fias_id'],
            )
            return cached

        # Определяем ФИАС через выбранного провайдера
        if self.provider == 'dadata':
            result = self._get_fias_from_dadata(ip_address)
        else:
            logger.error(
                'Неизвестный GEO_PROVIDER: %s',
                self.provider,
            )
            result = self._get_default_fias()

        # Кэшируем на сутки
        if result and result.get('city_fias_id'):
            cache.set(cache_key, result, 86400)
        else:
            logger.warning(
                'ФИАС не определен для IP: %s provider=%s',
                ip_address,
                self.provider,
            )

        return result

    def _get_fias_from_dadata(self, ip_address) -> dict:
        """Сервис DaData (iplocate)."""
        api_key = getattr(settings, 'DADATA_API_KEY', None)

        if not api_key:
            logger.error('DADATA_API_KEY не задан в settings')
            return self._get_default_fias()

        try:
            response = requests.post(
                'https://suggestions.dadata.ru/suggestions/api/4_1/rs/iplocate/address',
                json={'ip': ip_address},
                headers={
                    'Authorization': f'Token {api_key}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                timeout=(2, 2),
            )

            if response.status_code != 200:
                logger.warning(
                    'DaData HTTP error status=%s body=%s ip=%s',
                    response.status_code,
                    response.text,
                    ip_address,
                )
                return self._get_default_fias()

            payload = response.json()

            location = payload.get('location')
            if not location:
                logger.info(
                    'DaData: location пустой для IP: %s payload=%s',
                    ip_address,
                    payload,
                )
                return self._get_default_fias()

            data = location.get('data') or {}

            if data.get('country_iso_code') != 'RU':
                logger.info(
                    'DaData: не RU IP  ip=%s country=%s',
                    ip_address,
                    data.get('country_iso_code'),
                )
                return self._get_default_fias()

            city_fias_id = data.get('city_fias_id')

            if not city_fias_id:
                logger.info(
                    'DaData: ФИАС не найден для IP: %s',
                    ip_address,
                )
                return self._get_default_fias()

            result = {
                'city_fias_id': city_fias_id,
            }

            logger.info(
                'DaData: определён ФИАС=%s ip=%s',
                city_fias_id,
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
            return self._get_default_fias()

    def _get_default_fias(self) -> dict:
        """ФИАС по умолчанию."""
        return {
            'city_fias_id': getattr(
                settings,
                'DEFAULT_FIAS',
                '0c5b2444-70a0-4932-980c-b4dc0d3f02b5',
            ),
        }
