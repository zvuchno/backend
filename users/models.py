from django.contrib.auth.models import AbstractUser
from django.db import models

from .constants import EMAIL_FIELD_MAX_LENGTH


class CoreUser(AbstractUser):
    """Кастомная модель пользователя."""

    email = models.EmailField(
        unique=True,
        max_length=EMAIL_FIELD_MAX_LENGTH,
    )

    REQUIRED_FIELDS = ['email', ]

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'пользователи'
        ordering = ['-date_joined', 'username']

    def __str__(self):
        return self.username
