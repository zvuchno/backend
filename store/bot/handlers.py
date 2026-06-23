import logging

from .telegram import bot
from users.models import ArtistProfile

logger = logging.getLogger(__name__)


@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обрабатывает /start, привязывает chat_id к артисту по токену."""
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
