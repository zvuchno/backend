"""Сериализаторы для управления учетной записью."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from users.services import get_user_from_uid, verify_email_token

User = get_user_model()


class MeSerializer(serializers.ModelSerializer):
    """Сериализатор текущего пользователя."""

    is_listener = serializers.SerializerMethodField()
    is_artist = serializers.SerializerMethodField()

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

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'is_email_verified',
            'is_listener',
            'is_artist',
        )


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
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
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
