"""Сериализаторы регистрации слушателя."""

from django.contrib.auth import get_user_model
from django.db import transaction

from .base_registration import BaseRegistrationSerializer
from .mixins import PhoneRegistrationMixin
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
        user = super().create(validated_data)
        ListenerProfile.objects.create(
            user=user,
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

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'phone', 'password')
