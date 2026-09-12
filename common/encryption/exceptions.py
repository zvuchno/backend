"""Исключения шифрования данных."""


class EncryptionConfigurationError(RuntimeError):
    """Ошибка конфигурации шифрования."""


class EncryptionKeyNotFoundError(RuntimeError):
    """Не найден ключ, которым зашифровано значение."""


class InvalidEncryptedValueError(ValueError):
    """Зашифрованное значение повреждено или имеет неизвестный формат."""
