from django.contrib.auth.models import AbstractUser
from django.db import models


class CoreUser(AbstractUser):
    """Кастомная модель пользователя."""

    email = models.EmailField(unique=True)

    REQUIRED_FIELDS = ['email', ]

    class Meta:
        verbose_name = 'учетная запись'
        verbose_name_plural = 'учетные записи'
        ordering = ['-date_joined', 'username']

    def __str__(self):
        return self.username
