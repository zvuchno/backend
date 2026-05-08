"""Сериализаторы юридических документов."""

from rest_framework import serializers

from users.models import ConsentDocument


class ConsentDocumentSerializer(serializers.ModelSerializer):
    """Сериализатор модели ConsentDocument."""

    class Meta:
        model = ConsentDocument
        fields = (
            'document_type',
            'version',
            'created_at',
        )


class ConsentDocumentDetailSerializer(ConsentDocumentSerializer):
    """Сериализатор для детального отображения документа."""

    class Meta(ConsentDocumentSerializer.Meta):
        fields = ConsentDocumentSerializer.Meta.fields + ('content',)
