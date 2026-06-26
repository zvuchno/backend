import logging

from telebot.apihelper import ApiTelegramException

from store.bot.telegram import get_bot

logger = logging.getLogger(__name__)


def send_telegram_message(chat_id: int, message: str) -> None:
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot = get_bot()
    except Exception as e:
        logger.error('Ошибка инициализации бота в telegram_message: %s', e)
        return

    logger.debug('Bot-Telegram: Отправка сообщения')
    try:
        bot.send_message(chat_id, message)
    except ApiTelegramException as e:
        logger.error('Не удалось отправить сообщение в Telegram: %s', e)
        raise
    except Exception:
        logger.exception(
            'Непредвиденная ошибка при отправке сообщения в Telegram',
        )
        raise

    logger.debug('Bot-Telegram: Сообщение успешно отправлено')
