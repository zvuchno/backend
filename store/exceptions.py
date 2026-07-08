"""Кастомные исключения, приложения store."""


class CDEKIntegrationError(Exception):
    """Ошибка при работе с API СДЭК."""

    def __init__(self, message='Сервис доставки временно недоступен.'):
        """Инициализация исключения."""
        super().__init__(message)


class AudioProcessingError(Exception):
    """Ошибка подготовки производного аудиофайла."""


class TemporaryAudioStorageError(AudioProcessingError):
    """Временная ошибка доступа к аудиофайлу в storage."""
