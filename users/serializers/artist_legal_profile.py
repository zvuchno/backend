"""Сериализаторы юр профиля."""

from django.db import transaction
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers

from users.models import (
    ArtistBankData,
    ArtistCompanyData,
    ArtistIdentityData,
    ArtistLegalProfile,
)


class ArtistIdentityDataSerializer(serializers.ModelSerializer):
    """Сериализатор паспортных данных артиста."""

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
            'inn',
        )


class ArtistBankDataSerializer(serializers.ModelSerializer):
    """Сериализатор банковских данных артиста."""

    class Meta:
        model = ArtistBankData
        fields = (
            'id',
            'bank_name',
            'bik',
            'correspondent_account',
            'checking_account',
        )


class ArtistCompanyDataSerializer(serializers.ModelSerializer):
    """Сериализатор данных юридического лица."""

    class Meta:
        model = ArtistCompanyData
        fields = (
            'id',
            'company_name',
            'company_address',
            'inn',
            'ogrn',
        )


class ArtistLegalProfileSerializer(serializers.ModelSerializer):
    """Сериализатор юридического профиля артиста."""

    phone = PhoneNumberField(required=False, allow_blank=True, allow_null=True)
    is_verified = serializers.BooleanField(read_only=True)
    comment = serializers.CharField(read_only=True)

    class Meta:
        model = ArtistLegalProfile
        fields = (
            'id',
            'email',
            'phone',
            'recipient_type',
            'is_verified',
            'comment',
        )


class ArtistLegalSerializer(serializers.Serializer):
    """Агрегирующий сериализатор юридических данных артиста."""

    legal_profile = ArtistLegalProfileSerializer(
        source='*',  # получит весь instance
        required=False,
    )
    identity_data = ArtistIdentityDataSerializer(
        required=False,
        allow_null=True,
    )
    bank_data = ArtistBankDataSerializer(
        required=False,
        allow_null=True,
    )

    company_data = ArtistCompanyDataSerializer(
        required=False,
        allow_null=True,
    )

    @staticmethod
    def _update_items(instance, data) -> None:
        """Заполняет значения полей модели."""
        for key, value in data.items():
            setattr(instance, key, value)

    @transaction.atomic
    def update(self, instance, validated_data):
        """Обновляет юридический профиль и связанные блоки данных."""
        identity_data = validated_data.pop('identity_data', None)
        bank_data = validated_data.pop('bank_data', None)
        company_data = validated_data.pop('company_data', None)
        legal_profile = validated_data

        if legal_profile:
            self._update_items(instance, legal_profile)
            instance.save()
        if identity_data is not None:
            identity_data_instance, _ = (
                ArtistIdentityData.objects.get_or_create(
                    legal_profile=instance,
                )
            )
            self._update_items(identity_data_instance, identity_data)
            identity_data_instance.save()
        if bank_data is not None:
            bank_data_instance, _ = ArtistBankData.objects.get_or_create(
                legal_profile=instance,
            )
            self._update_items(bank_data_instance, bank_data)
            bank_data_instance.save()
        if company_data is not None:
            company_data_instance, _ = ArtistCompanyData.objects.get_or_create(
                legal_profile=instance,
            )
            self._update_items(company_data_instance, company_data)
            company_data_instance.save()

        instance.refresh_from_db()

        return instance

    def validate(self, attrs) -> dict:
        recipient_type = attrs.get(
            'recipient_type',
            getattr(self.instance, 'recipient_type', None),
        )
        company_data = attrs.get('company_data')
        if (
            recipient_type != ArtistLegalProfile.RecipientType.LEGAL_ENTITY
            and company_data is not None
        ):
            raise serializers.ValidationError({
                'company_data': (
                    'Данные юридического лица допустимы только '
                    'для получателя типа "Юридическое лицо".'
                ),
            })
        return attrs
