"""Кастомные исключения, приложения store."""


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
