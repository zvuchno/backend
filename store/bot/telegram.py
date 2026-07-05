"""Модуль инициализации Telegram-бота.

Содержит единственный экземпляр bot, который используется во всем приложении.
"""

import logging

from django.conf import settings
from telebot import TeleBot, apihelper

logger = logging.getLogger(__name__)

_bot_instance = None


def get_bot() -> TeleBot:
    """Фабрика для получения экземпляра бота.

    Инициализирует бота при первом обращении, настраивает прокси.
    """
    global _bot_instance

    if _bot_instance is None:
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)

        if not token:
            logger.error('TELEGRAM_BOT_TOKEN не задан в настройках!')
            raise ValueError('TELEGRAM_BOT_TOKEN is missing')

        # Если в .env задан TELEGRAM_PROXY_URL, настраиваем прокси
        proxy_url = getattr(settings, 'TELEGRAM_PROXY_URL', None)
        if proxy_url:
            cleaned_proxy = str(proxy_url).strip().replace(' ', '')
            apihelper.proxy = {
                'http': cleaned_proxy,
                'https': cleaned_proxy,
            }
            logger.info('Прокси для Telegram успешно настроен')

        # Инициализация бота
        _bot_instance = TeleBot(token=token, threaded=False)
        logger.debug('Экземпляр TeleBot успешно создан')

    return _bot_instance
