"""Сериализаторы юр профиля."""

from rest_framework import serializers

from users.models import (
    ArtistBankData,
    ArtistIdentityData,
    ArtistLegalProfile,
)


class ArtistIdentityDataSerializer(serializers.ModelSerializer):
    """TODO."""

    class Meta:
        model = ArtistIdentityData
        fields = (
            'id',
            'first_name',
            'last_name',
            'middle_name',
            'birth_date',
            'registration_address',
            'passport_series',
            'passport_number',
            'passport_issued_by',
            'passport_issue_date',
        )


class ArtistBankDataSerializer(serializers.ModelSerializer):
    """TODO."""

    class Meta:
        model = ArtistBankData
        fields = (
            'id',
            'bank_name',
            'bik',
            'inn',
            'correspondent_account',
            'checking_account',
        )


class ArtistLegalProfileSerializer(serializers.ModelSerializer):
    """TODO."""

    is_verified = serializers.BooleanField(read_only=True)
    comment = serializers.CharField(read_only=True)

    class Meta:
        model = ArtistLegalProfile
        fields = (
            'id',
            'user',
            'recipient_type',
            'recipient_name',
            'taxation_system',
            'is_verified',
            'comment',
        )


class ArtistLegalSerializer(serializers.Serializer):
    """TODO."""

    legal_profile = ArtistLegalProfileSerializer(
        required=True,
    )
    identity_data = ArtistIdentityDataSerializer(
        required=False,
        allow_null=True,
    )
    bank_data = ArtistBankDataSerializer(
        required=False,
        allow_null=True,
    )

    def to_representation(self, instance):
        identity_data = getattr(instance, 'identity_data', None)
        bank_data = getattr(instance, 'bank_data', None)
        return {
            'legal_profile': ArtistLegalProfileSerializer(instance).data,
            'identity_data': (
                ArtistIdentityDataSerializer(identity_data).data
                if identity_data
                else None
            ),
            'bank_data': (
                ArtistBankDataSerializer(bank_data).data if bank_data else None
            ),
        }
