"""Методы нормализации."""


def normalize_email(email: str) -> str:
    """Нормализация email."""
    return email.strip().lower()


def normalize_digits(value: str) -> str:
    """Возвращает строку, содержащую только цифры из исходного значения."""
    if not value:
        return ''
    return ''.join(d for d in str(value) if d.isdigit())
