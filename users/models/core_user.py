from django.contrib.auth.models import AbstractUser
from django.db import models


class CoreUser(AbstractUser):
    """Кастомная модель пользователя."""

    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', ]

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'пользователи'
        ordering = ['-date_joined', 'username']

    def __str__(self):
        return self.username
