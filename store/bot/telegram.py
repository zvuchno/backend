"""Модуль инициализации Telegram-бота.

Содержит единственный экземпляр bot, который используется во всем приложении.
"""

from django.conf import settings
from telebot import TeleBot

# Экземпляр бота, используемый для взаимодействия с API Telegram
bot = TeleBot(token=settings.TELEGRAM_BOT_TOKEN)
