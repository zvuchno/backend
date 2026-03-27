"""Сериализаторы профиля слушателя."""

from rest_framework import serializers

from users.models import ListenerProfile


class ListenerMeSerializer(serializers.ModelSerializer):
    """Сериализатор профиля слушателя."""

    class Meta:
        model = ListenerProfile
        fields = ('full_name',)
