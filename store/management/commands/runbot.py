import logging
import time

from django.core.management.base import BaseCommand
from telebot.apihelper import ApiTelegramException

from store.bot.handlers import register_handlers
from store.bot.telegram import get_bot

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Запуск Telegram-бота."""

    help = 'Запуск Telegram-бота'

    def handle(self, *args, **options):

        try:
            bot = get_bot()
        except Exception as e:
            logger.error('Не удалось запустить бота: %s', e)
            return
        register_handlers(bot)

        logger.info('Telegram bot запущен')

        while True:
            try:
                bot.infinity_polling(
                    skip_pending=True,
                    timeout=30,
                    long_polling_timeout=30,
                )
            except ApiTelegramException as e:
                logger.error('Ошибка Telegram API: %s', e)
                time.sleep(5)
            except Exception:
                logger.exception(
                    'Критическая ошибка Telegram бота, '
                    'перезапуск через 5 секунд...',
                )
                time.sleep(5)
