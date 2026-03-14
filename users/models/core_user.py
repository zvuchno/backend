"""Пользовательская модель приложения.

Модуль содержит кастомную модель пользователя,
используемую в проекте в качестве основной модели
для аутентификации и связи с профилями ролей.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class CoreUser(AbstractUser):
    """Кастомная модель пользователя.

    Расширяет стандартную модель Django и использует email
    как основное поле для входа в систему. Дополнительно
    сохраняет username для отображения и совместимости
    с механизмами Django и сторонних библиотек.
    """

    email = models.EmailField(unique=True)

    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = 'пользователь'
        verbose_name_plural = 'пользователи'
        ordering = ('-date_joined', 'username')

    def __str__(self):
        """Возвращает строковое представление пользователя."""
        return self.email
