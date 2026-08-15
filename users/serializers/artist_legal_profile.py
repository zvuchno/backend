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

    is_ready_for_verification = serializers.BooleanField(read_only=True)
    verification_missing_fields = serializers.SerializerMethodField()

    class Meta:
        model = ArtistLegalProfile
        fields = (
            'email',
            'phone',
            'recipient_type',
            'is_verified',
            'is_ready_for_verification',
            'verification_missing_fields',
            'comment',
        )

    def get_verification_missing_fields(self, obj):
        """Возвращает незаполненные поля, необходимые для проверки."""
        return obj.get_verification_missing_fields()


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
    def _update_items(instance, data) -> bool:
        """Обновляет поля модели и возвращает признак изменений."""
        changed = False
        for key, value in data.items():
            if getattr(instance, key) != value:
                setattr(instance, key, value)
                changed = True
        return changed

    @transaction.atomic
    def update(self, instance, validated_data):
        """Обновляет юридический профиль и связанные блоки данных."""
        identity_data = validated_data.pop('identity_data', None)
        bank_data = validated_data.pop('bank_data', None)
        company_data = validated_data.pop('company_data', None)
        legal_profile = validated_data
        reset_verified = False

        if legal_profile:
            changed = self._update_items(instance, legal_profile)
            reset_verified |= changed
            if changed:
                instance.save()
        if identity_data is not None:
            identity_data_instance, _ = (
                ArtistIdentityData.objects.get_or_create(
                    legal_profile=instance,
                )
            )
            changed = self._update_items(identity_data_instance, identity_data)
            reset_verified |= changed
            if changed:
                identity_data_instance.save()
        if bank_data is not None:
            bank_data_instance, _ = ArtistBankData.objects.get_or_create(
                legal_profile=instance,
            )
            changed = self._update_items(bank_data_instance, bank_data)
            reset_verified |= changed
            if changed:
                bank_data_instance.save()
        if company_data is not None:
            company_data_instance, _ = ArtistCompanyData.objects.get_or_create(
                legal_profile=instance,
            )
            changed = self._update_items(company_data_instance, company_data)
            reset_verified |= changed
            if changed:
                company_data_instance.save()

        if reset_verified and instance.is_verified:
            instance.is_verified = False
            instance.save(update_fields=('is_verified',))

        return instance
