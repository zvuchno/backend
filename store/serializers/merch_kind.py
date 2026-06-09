from rest_framework import serializers

from store.models import MerchKind


class MerchKindSerializer(serializers.ModelSerializer):
    """Сериализатор для типов мерча."""

    class Meta:
        model = MerchKind
        fields = ('id', 'name', 'slug')
