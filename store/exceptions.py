"""Кастомные исключения, приложения store."""

from rest_framework.exceptions import APIException
from rest_framework.status import HTTP_400_BAD_REQUEST

PUBLICATION_BLOCKED_DETAIL = 'Невозможно опубликовать товар.'


class CDEKIntegrationError(Exception):
    """Ошибка при работе с API СДЭК."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        error: str | None = None,
    ):
        """Инициализация исключения."""
        super().__init__(message)
        self.code = code
        self.error = error


class AudioProcessingError(Exception):
    """Ошибка подготовки производного аудиофайла."""


class TemporaryAudioStorageError(AudioProcessingError):
    """Временная ошибка доступа к аудиофайлу в storage."""


class NotEnoughStock(Exception):
    """Недостаточно товара на складе."""


class PromocodeNotAvailable(Exception):
    """Промокод недоступен для применения."""


class ReceiptValidationError(ValueError):
    """Ошибка формирования или проверки фискального чека."""


class PublicationBlocked(APIException):
    """Ошибка невозможности публикации товара."""

    status_code = HTTP_400_BAD_REQUEST
    default_code = 'publication_blocked'

    def __init__(self, reasons):
        """Создаёт ошибку публикации со списком причин блокировки."""
        super().__init__({
            'detail': PUBLICATION_BLOCKED_DETAIL,
            'reasons': reasons,
        })
