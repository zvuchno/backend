import logging

from celery import shared_task
from telebot.apihelper import ApiTelegramException

from store.services.telegram_sender import send_telegram_message
from users.models import ArtistProfile

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def send_telegram_notification(self, artist_id: int, message: str) -> bool:
    """Отправка уведомления в Telegram."""
    try:
        artist = ArtistProfile.objects.get(id=artist_id)
    except ArtistProfile.DoesNotExist:
        logger.warning(
            'Telegram task: артист не найден (artist_id=%s)',
            artist_id,
        )
        return False

    if not artist.telegram_chat_id:
        logger.info(
            'Telegram task: у артиста не подключён Telegram (artist_id=%s)',
            artist_id,
        )
        return False

    try:
        return send_telegram_message(
            artist.telegram_chat_id,
            message,
        )

    except ApiTelegramException as exc:
        logger.warning(
            'Telegram task: ошибка Telegram API (artist_id=%s)',
            artist_id,
        )

        raise self.retry(exc=exc)
