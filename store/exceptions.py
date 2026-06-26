"""Кастомные исключения, приложения store."""


class CDEKIntegrationError(Exception):
    """Ошибка при работе с API СДЭК."""

    def __init__(self, message='Сервис доставки временно недоступен.'):
        """Инициализация исключения."""
        self.message = message
        super().__init__(self.message)


class AudioProcessingError(Exception):
    """Ошибка подготовки производного аудиофайла."""
