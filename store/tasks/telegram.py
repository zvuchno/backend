import logging

from celery import shared_task
from requests.exceptions import RequestException
from telebot.apihelper import ApiException, ApiTelegramException

from store.services.telegram_sender import (
    send_telegram_document,
    send_telegram_message,
)
from users.models import ArtistProfile

logger = logging.getLogger(__name__)

NON_RETRYABLE_CODES = (400, 403)
MAX_RETRY_DELAY = 300


def _retry_delay(retries: int, base: int, exc: Exception) -> int:
    """Возвращает паузу перед повтором.

    При лимитах (429) Telegram сам говорит, сколько ждать, иначе
    пауза растёт экспоненциально, но не больше MAX_RETRY_DELAY.
    """
    if isinstance(exc, ApiTelegramException):
        parameters = (exc.result_json or {}).get('parameters') or {}
        retry_after = parameters.get('retry_after')
        if retry_after:
            return retry_after
    return min(base * 2**retries, MAX_RETRY_DELAY)


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=10,
    rate_limit='25/s',
)
def send_telegram_notification(
    self,
    artist_id: int,
    message: str,
    document_path: str | None = None,
    document_name: str | None = None,
) -> bool:
    """Отправка уведомления в Telegram, с файлом или без."""
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
        if document_path:
            return send_telegram_document(
                artist.telegram_chat_id,
                document_path,
                document_name,
                caption=message,
            )
        return send_telegram_message(artist.telegram_chat_id, message)

    except ApiTelegramException as exc:
        if exc.error_code in NON_RETRYABLE_CODES:
            logger.warning(
                'Telegram task: сообщение отклонено, ретрай не нужен '
                '(artist_id=%s): %s',
                artist_id,
                exc,
            )
            return False

        logger.warning(
            'Telegram task: ошибка Telegram API (artist_id=%s): %s',
            artist_id,
            exc,
        )
        raise self.retry(
            exc=exc,
            countdown=_retry_delay(
                self.request.retries,
                self.default_retry_delay,
                exc,
            ),
        )

    except (RequestException, ApiException, OSError) as exc:
        logger.warning(
            'Telegram task: временная ошибка (artist_id=%s): %s',
            artist_id,
            exc,
        )
        raise self.retry(
            exc=exc,
            countdown=_retry_delay(
                self.request.retries,
                self.default_retry_delay,
                exc,
            ),
        )
