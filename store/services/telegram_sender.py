import logging

from telebot.apihelper import ApiTelegramException

from store.bot.telegram import bot

logger = logging.getLogger(__name__)


def send_telegram_message(chat_id: int, message: str) -> bool:
    """Отправляет сообщение в Telegram-чат."""
    logger.debug('Bot-Telegram: Отправка сообщения')
    try:
        bot.send_message(chat_id, message)
    except ApiTelegramException:
        logger.exception('Не удалось отправить сообщение в Telegram')
        return False

    logger.debug('Bot-Telegram: Сообщение успешно отправлено')
    return True
