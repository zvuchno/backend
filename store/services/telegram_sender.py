import logging

from django.core.files.storage import default_storage
from telebot.apihelper import ApiTelegramException

from store.bot.telegram import get_bot

logger = logging.getLogger(__name__)


def send_telegram_message(chat_id: int, message: str) -> bool:
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot = get_bot()
    except Exception as e:
        logger.error('Ошибка инициализации бота в telegram_message: %s', e)
        return False

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

    return True


def send_telegram_document(
    chat_id: int,
    document_path: str,
    filename: str,
    caption: str,
) -> bool:
    """Отправляет файл из хранилища в Telegram-чат с подписью.

    Возвращает False, если бот не инициализирован или файла нет.
    Остальные ошибки пробрасываются, чтобы таска могла сделать ретрай.
    """
    try:
        bot = get_bot()
    except Exception as e:
        logger.error('Ошибка инициализации бота в telegram_document: %s', e)
        return False

    try:
        file = default_storage.open(document_path, 'rb')
    except FileNotFoundError:
        logger.error(
            'Telegram: файл не найден в хранилище: %s',
            document_path,
        )
        return False

    with file:
        try:
            bot.send_document(
                chat_id,
                file,
                caption=caption,
                visible_file_name=filename,
            )
        except ApiTelegramException as e:
            logger.error('Не удалось отправить документ в Telegram: %s', e)
            raise

    return True
