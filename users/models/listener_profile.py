from django.contrib.auth import get_user_model
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


User = get_user_model()


PHONE_FIELD_MAX_LENGTH = 50


class ListenerProfile(models.Model):
    """Модель слушателя."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='listener_profile',
    )
    phone = PhoneNumberField(
        'Номер телефона',
        max_length=PHONE_FIELD_MAX_LENGTH,
        help_text='Номер телефона',
    )

    class Meta:
        verbose_name = 'Слушатель'
        verbose_name_plural = 'слушатели'

    def __str__(self):
        return self.user.username
