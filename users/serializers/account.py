"""Сериализаторы для управления учетной записью."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError
from rest_framework import serializers

from users.serializers.mixins import PhoneRegistrationMixin
from users.services import (
    get_user_from_uid,
    set_user_password,
    verify_email_token,
    verify_password_reset_token,
)

User = get_user_model()


class EmptySerializer(serializers.Serializer):
    """Пустой сериализатор для ручек без тела запроса."""

    pass


class MeSerializer(serializers.ModelSerializer):
    """Сериализатор текущего пользователя."""

    is_listener = serializers.SerializerMethodField()
    is_artist = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'phone',
            'is_phone_verified',
            'is_email_verified',
            'is_listener',
            'is_artist',
        )

    @staticmethod
    def get_is_listener(obj) -> bool:
        """Определяет, есть ли активный профиль слушателя."""
        profile = getattr(obj, 'listener_profile', None)
        return bool(profile and profile.is_active)

    @staticmethod
    def get_is_artist(obj) -> bool:
        """Определяет, есть ли активный профиль артиста."""
        profile = getattr(obj, 'artist_profile', None)
        return bool(profile and profile.is_active)


class ChangePasswordSerializer(serializers.Serializer):
    """Сериализатор смены пароля пользователя."""

    old_password = serializers.CharField(
        write_only=True,
        label='Старый пароль',
    )
    new_password = serializers.CharField(
        write_only=True,
        label='Новый пароль',
    )
    retype_new_password = serializers.CharField(
        write_only=True,
        label='Подтверждение нового пароля',
    )

    def validate_old_password(self, value):
        """Проверяет корректность текущего пароля."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(
                'Текущий пароль указан неверно.',
            )
        return value

    def validate(self, attrs):
        """Проверяет совпадение и валидность нового пароля."""
        new_password = attrs.get('new_password')
        retype_new_password = attrs.get('retype_new_password')
        if new_password != retype_new_password:
            raise serializers.ValidationError({
                'retype_new_password': 'Новые пароли не совпадают.',
            })
        validate_password(new_password, self.context['request'].user)
        return attrs

    def save(self, **kwargs):
        """Устанавливает новый пароль пользователю."""
        user = self.context['request'].user
        set_user_password(user, self.validated_data['new_password'])
        return user


class EmailVerificationSerializer(serializers.Serializer):
    """Сериализатор подтверждения email по uid и токену."""

    uid = serializers.CharField(
        write_only=True,
        label='Идентификатор пользователя',
    )
    token = serializers.CharField(
        write_only=True,
        label='Токен подтверждения',
    )

    def validate(self, attrs):
        """Проверяет корректность uid и токена."""
        user = get_user_from_uid(attrs.get('uid'), User)
        token = attrs.get('token', None)

        if not user:
            raise serializers.ValidationError({
                'uid': 'Пользователь не найден.',
            })
        if not verify_email_token(user, token):
            raise serializers.ValidationError({
                'token': 'Ссылка недействительна.',
            })
        attrs['user'] = user
        return attrs

    def save(self, **kwargs):
        """Отмечает email пользователя как подтвержденный."""
        user = self.validated_data['user']
        if not user.is_email_verified:
            user.is_email_verified = True
            user.save(update_fields=['is_email_verified'])
        return user


class PhoneChangeSerializer(
    PhoneRegistrationMixin,
    serializers.ModelSerializer,
):
    """Сериализатор для изменения телефона аккаунта."""

    class Meta:
        model = User
        fields = ('phone',)

    def update(self, instance, validated_data):
        """Сохраняет телефон и меняет его флаг на неподтвержденный."""
        new_phone = validated_data.get('phone')
        if instance.phone == new_phone:
            return instance
        instance.phone = new_phone
        instance.is_phone_verified = False
        instance.save(update_fields=['is_phone_verified', 'phone'])
        return instance


class PasswordResetRequestSerializer(serializers.Serializer):
    """Сериализатор запроса на восстановление пароля."""

    email = serializers.EmailField(
        label='Email',
        write_only=True,
    )


class PasswordResetVerifySerializer(serializers.Serializer):
    """Сериализатор проверки ссылки восстановления пароля."""

    uid = serializers.CharField(
        label='Идентификатор пользователя',
        write_only=True,
    )
    token = serializers.CharField(
        label='Токен восстановления пароля',
        write_only=True,
    )

    def validate(self, attrs):
        """Проверка токена."""
        user = get_user_from_uid(attrs.get('uid'), User)
        if not user:
            raise serializers.ValidationError({
                'uid': 'Пользователь не найден.',
            })

        token = attrs.get('token')
        if not verify_password_reset_token(user, token):
            raise serializers.ValidationError({
                'token': 'Ссылка недействительна.',
            })

        attrs['user'] = user
        return attrs


class PasswordResetConfirmSerializer(PasswordResetVerifySerializer):
    """Сериализатор установки нового пароля."""

    new_password = serializers.CharField(
        label='Новый пароль',
        write_only=True,
    )
    retype_new_password = serializers.CharField(
        label='Повторный ввод пароля',
        write_only=True,
    )

    def validate(self, attrs):
        """Проверка токена, пользователя и нового пароля."""
        attrs = super().validate(attrs)
        new_password = attrs.get('new_password')
        retype_new_password = attrs.get('retype_new_password')
        user = attrs['user']

        if new_password != retype_new_password:
            raise serializers.ValidationError({
                'retype_new_password': 'Пароли не совпадают.',
            })
        validate_password(new_password, user)
        return attrs

    def save(self, **kwargs):
        """Устанавливает новый пароль пользователю."""
        user = self.validated_data['user']
        set_user_password(user, self.validated_data['new_password'])
        return user


class UsernameChangeSerializer(serializers.ModelSerializer):
    """Меняет username."""

    def validate_username(self, value):
        current_user = self.instance
        value = value.strip()
        if current_user.username == value:
            raise serializers.ValidationError('Username совпадает с текущим.')
        if (
            User.objects
            .filter(
                username=value,
            )
            .exclude(pk=current_user.pk)
            .exists()
        ):
            raise serializers.ValidationError('Username занят.')
        return value

    def update(self, instance, validated_data):
        current_user = self.instance
        instance.username = validated_data['username']
        try:
            instance.save(update_fields=['username'])
        except IntegrityError:
            if (
                User.objects
                .filter(
                    username=validated_data['username'],
                )
                .exclude(pk=current_user.pk)
                .exists()
            ):
                raise serializers.ValidationError(
                    {'username': 'Username занят.'},
                )
            raise
        return instance

    class Meta:
        model = User
        fields = ('username',)
