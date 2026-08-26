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


class ConsentRequirementSerializer(serializers.Serializer):
    """Требования согласий для одного сценария."""

    required = serializers.ListField(
        child=serializers.CharField(),
    )
    optional = serializers.ListField(
        child=serializers.CharField(),
    )


class ConsentRequirementsSerializer(serializers.Serializer):
    """Справочник требований согласий по сценариям."""

    listener_registration = ConsentRequirementSerializer()
    artist_onboarding = ConsentRequirementSerializer()
    label_onboarding = ConsentRequirementSerializer()
    checkout = ConsentRequirementSerializer()
