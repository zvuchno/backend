"""Модуль моделей юридических документов и согласий пользователя."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from users.models.abstract import TimestampModel


class UserConsent(TimestampModel):
    """Согласие пользователя на обработку данных и другие юридические действия.

    Хранит факт принятия пользователем конкретного типа согласия,
    включая контекст, в котором оно было дано.

    Используется для:
    - подтверждения юридически значимых действий пользователя
    - хранения истории согласий
    - аудита и разрешения спорных ситуаций

    Особенности:
    - может быть привязано к заказу (согласие при оформлении)
    - хранит версию документа, с которым согласился пользователь
    - можно согласиться только с активным в настоящий момент документом
    - фиксирует технические данные (IP, User-Agent)
    - хранит объкт подписки (artist) TODO: вынести подписки в отдельную модель.
    """

    email = models.EmailField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='consents',
        verbose_name='Пользователь',
    )
    order = models.ForeignKey(
        'store.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='consents',
        verbose_name='Связанный заказ',
    )
    artist = models.ForeignKey(
        'users.ArtistProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='consents',
        verbose_name='Объект подписки',
    )
    accepted_at = models.DateTimeField(
        'Дата соглашения',
        auto_now_add=True,
        help_text='Дата и время принятия согласия',
    )
    ip_address = models.GenericIPAddressField(
        'IP-address',
        null=True,
        blank=True,
        help_text='IP-адрес пользователя в момент принятия',
    )
    user_agent = models.TextField(
        'Пользовательский агент',
        null=True,
        blank=True,
        help_text='Agent клиента пользователя',
    )
    document = models.ForeignKey(
        'users.ConsentDocument',
        on_delete=models.PROTECT,
        verbose_name='Принятый документ',
    )

    def clean(self):
        super().clean()
        if not self.document_id:
            raise ValidationError({
                'document': 'Согласие не может существовать '
                'без ссылки на юридический документ.',
            })
        if not self.pk and self.document_id:
            if not self.document.is_active:
                raise ValidationError({
                    'document': (
                        f'Документ "{self.document}" больше не активен. '
                        'Пользователь должен согласиться с актуальной версией.'
                    ),
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'согласие пользователя'
        verbose_name_plural = 'согласия пользователя'
        ordering = ('-created_at',)

    def __str__(self):
        return (
            f'{self.user.email if self.user else self.email} → '
            f'[ {self.document} ]'
        )
