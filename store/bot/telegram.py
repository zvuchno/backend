"""Модуль инициализации Telegram-бота.

Содержит единственный экземпляр bot, который используется во всем приложении.
"""

from django.conf import settings
from telebot import TeleBot, apihelper

# Если в .env задан TELEGRAM_PROXY_URL, настраиваем прокси
proxy_url = getattr(settings, 'TELEGRAM_PROXY_URL', None)

if proxy_url:
    cleaned_proxy = str(proxy_url).strip().replace(' ', '')

    apihelper.proxy = {
        'http': cleaned_proxy,
        'https': cleaned_proxy,
    }

# Экземпляр бота, используемый для взаимодействия с API Telegram
bot = TeleBot(token=settings.TELEGRAM_BOT_TOKEN, threaded=False)
