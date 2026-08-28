"""Сериализаторы регистрации слушателя."""

from django.contrib.auth import get_user_model
from django.db import transaction

from common.utils import get_client_ip, get_user_agent

from ..services import ConsentService
from .base_registration import BaseRegistrationSerializer
from .mixins import PhoneRegistrationMixin
from users.consents_policy import ConsentScenario
from users.models import ListenerProfile

User = get_user_model()


class ListenerRegistrationSerializer(
    PhoneRegistrationMixin,
    BaseRegistrationSerializer,
):
    """Сериализатор регистрации слушателя.

    Создает пользователя, а затем связанный с ним профиль слушателя.
    Дополнительно принимает номер телефона, проверяет его
    и возвращает в ответе после успешной регистрации.
    """

    @transaction.atomic
    def create(self, validated_data):
        """Создает пользователя и профиль слушателя.

        Сначала создает объект пользователя средствами базового
        сериализатора, затем создает связанный профиль слушателя
        с переданным номером телефона. Операция выполняется атомарно.
        """
        accepted_types = set(validated_data.pop('consents', ()))
        user = super().create(validated_data)
        ListenerProfile.objects.create(
            user=user,
        )

        request = self.context.get('request')

        ConsentService.accept(
            scenario=ConsentScenario.LISTENER_REGISTRATION,
            accepted_types=accepted_types,
            user=user,
            email=user.email,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        return user

    def to_representation(self, instance):
        """Добавляет номер телефона в данные ответа.

        Формирует стандартное представление пользователя
        и дополняет его данными из связанного профиля слушателя.
        """
        data = super().to_representation(instance)
        data['phone'] = str(instance.phone) if instance.phone else None
        return data

    def get_consent_scenario(self, attrs):
        return ConsentScenario.LISTENER_REGISTRATION

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'phone',
            'password',
            'consents',
        )
