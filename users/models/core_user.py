"""Кастомная модель пользователя."""

from django.contrib.auth.models import AbstractUser
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from common.utils import normalize_email


class CoreUser(AbstractUser):
    """Кастомная модель пользователя.

    Расширяет стандартную модель Django и использует email
    как основное поле для входа в систему. Дополнительно
    сохраняет username для отображения и совместимости
    с механизмами Django и сторонних библиотек.
    """

    email = models.EmailField(unique=True)
    phone = PhoneNumberField(
        'Номер телефона',
        help_text='Номер телефона',
        unique=True,
        null=True,
        blank=True,
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'phone']

    is_email_verified = models.BooleanField(
        'Email подтвержден',
        default=False,
    )
    is_phone_verified = models.BooleanField(
        'Телефон подтвержден',
        default=False,
    )

    def save(self, *args, **kwargs):
        if self.email:
            self.email = normalize_email(self.email)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'учетная запись'
        verbose_name_plural = 'учетные записи'
        ordering = ('-date_joined', 'username')

    def __str__(self):
        return self.email
