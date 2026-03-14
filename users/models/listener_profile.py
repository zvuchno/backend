from django.conf import settings
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


from users.constants import FULL_NAME_FIELD_MAX_LENGTH
from .abstract.activatable_model import ActivatableModel
from .abstract.timestamp_model import TimestampModel


class ListenerProfile(ActivatableModel, TimestampModel):
    """Модель слушателя."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='listener_profile',
    )
    phone = PhoneNumberField(
        'Номер телефона',
        help_text='Номер телефона',
        unique=True,
    )
    full_name = models.CharField(
        'Имя и фамилия',
        max_length=FULL_NAME_FIELD_MAX_LENGTH,
    )

    class Meta:
        verbose_name = 'Слушатель'
        verbose_name_plural = 'слушатели'
        ordering = ['-created_at']

    def __str__(self):
        return self.user.username
