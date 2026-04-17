"""Модуль моделей юридических документов и согласий пользователя."""

from django.conf import settings
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
    - фиксирует технические данные (IP, User-Agent)
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='consents',
    )
    order = models.ForeignKey(
        'store.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='consents',
    )
    accepted_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Дата и время принятия согласия',
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IP-адрес пользователя в момент принятия',
    )
    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text='User-Agent клиента пользователя',
    )
    document = models.ForeignKey(
        'ConsentDocument',
        on_delete=models.PROTECT,
    )

    class Meta:
        verbose_name = 'согласие пользователя'
        verbose_name_plural = 'согласия пользователя'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.user.email} → [ {self.document} ]'
