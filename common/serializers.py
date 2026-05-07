from rest_framework import serializers


class ChoiceSerializer(serializers.Serializer):
    """Сериализатор элемента справочника."""

    value = serializers.CharField()
    label = serializers.CharField()
