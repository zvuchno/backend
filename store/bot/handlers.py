import logging

from users.models import ArtistProfile

logger = logging.getLogger(__name__)


def register_handlers(bot):
    """Регистрирует все хендлеры на переданном экземпляре бота."""

    @bot.message_handler(commands=['start'])
    def handle_start(message) -> None:  # noqa: F841
        if message.chat.type != 'private':
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
            logger.warning('Привязка Telegram: токен не найден')
            bot.send_message(chat_id, 'Ссылка недействительна или устарела.')
            return

        artist.telegram_chat_id = chat_id
        artist.telegram_token = None
        artist.save(update_fields=['telegram_chat_id', 'telegram_token'])

        logger.info('Привязка Telegram выполнена: artist_id=%s', artist.id)
        bot.send_message(
            chat_id,
            '🎉 Готово! Уведомления подключены. '
            'Теперь вы будете получать уведомления '
            'о новых заказах в Telegram.',
        )
