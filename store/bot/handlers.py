import logging

from django.conf import settings
from telebot import TeleBot

from .telegram import get_bot
from users.models import ArtistProfile

logger = logging.getLogger(__name__)

token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
# Экземпляр для регистрации декоратора @bot.message_handlerc с фейковым токеном
bot = TeleBot(token=token if token else '0000000000:fake_token')


@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обрабатывает /start, привязывает chat_id к артисту по токену."""
    try:
        bot = get_bot()
    except Exception as e:
        logger.error('Ошибка инициализации бота в handle_start: %s', e)
        return

    if message.chat.type != 'private':  # Проверка: только личные сообщения
        bot.send_message(
            message.chat.id,
            '⚠️ Привязка аккаунта доступна только в личных сообщениях.',
        )
        return
    chat_id = message.chat.id
    args = message.text.split()

    if len(args) <= 1:
        bot.send_message(
            chat_id,
            'Используйте ссылку для подключения '
            'уведомлений из личного кабинета.',
        )
        return

    token = args[1]

    try:
        artist = ArtistProfile.objects.get(telegram_token=token)
    except ArtistProfile.DoesNotExist:
        logger.warning(
            'Не удалось выполнить привязку Telegram: токен не найден',
        )
        bot.send_message(
            chat_id,
            'Ссылка недействительна или устарела.',
        )
        return

    artist.telegram_chat_id = chat_id
    artist.telegram_token = None
    artist.save(
        update_fields=[
            'telegram_chat_id',
            'telegram_token',
        ],
    )

    logger.info(
        'Выполнена привязка Telegram для артиста: artist_id=%s',
        artist.id,
    )

    bot.send_message(
        chat_id,
        '🎉 Готово! Уведомления подключены. '
        'Теперь вы будете получать уведомления о новых заказах в Telegram.',
    )
