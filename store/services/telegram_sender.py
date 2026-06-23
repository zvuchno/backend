import logging

from telebot.apihelper import ApiTelegramException

from store.bot.telegram import bot

logger = logging.getLogger(__name__)


def send_telegram_message(chat_id: int, message: str) -> None:
    """Отправляет сообщение в Telegram-чат."""
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
