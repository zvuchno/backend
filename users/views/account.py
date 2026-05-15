"""Представления для управления учетной записью пользователя."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.generics import (
    GenericAPIView,
    RetrieveAPIView,
    UpdateAPIView,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from users.schemas import (
    change_password_schema,
    change_phone_schema,
    change_username_schema,
    email_verification_schema,
    me_schema,
    password_reset_confirm_schema,
    password_reset_request_schema,
    password_reset_verify_schema,
    resend_verification_email_schema,
)
from users.serializers import (
    ChangePasswordSerializer,
    EmailVerificationSerializer,
    EmptySerializer,
    MeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
    PhoneChangeSerializer,
    UsernameChangeSerializer,
)
from users.services import (
    build_email_verification_url,
    build_password_reset_url,
)

User = get_user_model()
logger = logging.getLogger(__name__)


@me_schema
class MeView(RetrieveAPIView):
    """Возвращает данные текущего пользователя."""

    serializer_class = MeSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """Возвращает пользователя из текущего запроса."""
        return self.request.user


@change_phone_schema
class ChangePhoneView(UpdateAPIView):
    """Представление смены телефона аккаунта."""

    permission_classes = [IsAuthenticated]
    serializer_class = PhoneChangeSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'change_phone'
    http_method_names = ['patch']

    def get_object(self):
        """Возвращает текущего пользователя."""
        return self.request.user


@change_password_schema
class ChangePasswordView(GenericAPIView):
    """Обрабатывает смену пароля пользователя."""

    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'change_password'

    def post(self, request, *args, **kwargs):
        """Валидирует данные и обновляет пароль пользователя."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'detail': 'Пароль успешно изменен.'},
            status=status.HTTP_200_OK,
        )


@email_verification_schema
class EmailVerificationView(GenericAPIView):
    """Подтверждает email пользователя по uid и токену."""

    permission_classes = [AllowAny]
    serializer_class = EmailVerificationSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'verify_email'

    def post(self, request, *args, **kwargs):
        """Проверяет данные и подтверждает email пользователя."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'detail': 'Email подтвержден.'},
            status=status.HTTP_200_OK,
        )


@resend_verification_email_schema
class ResendVerificationEmailView(GenericAPIView):
    """Повторно инициирует отправку письма подтверждения email."""

    permission_classes = [IsAuthenticated]
    serializer_class = EmptySerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'resend_verification_email'

    def post(self, request, *args, **kwargs):
        """Генерирует ссылку подтверждения и логирует ее."""
        user = request.user

        if user.is_email_verified:
            return Response(
                {'detail': 'Email уже подтвержден.'},
                status=status.HTTP_200_OK,
            )

        frontend_base_url = settings.FRONTEND_VERIFY_EMAIL_URL

        verification_url = build_email_verification_url(
            user=user,
            frontend_base_url=frontend_base_url,
        )
        response_data = {
            'detail': 'Запрос на подтверждение Email принят.',
        }
        if settings.DEBUG:
            response_data['debug_verification_url'] = verification_url

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )


@password_reset_request_schema
class PasswordResetRequestView(GenericAPIView):
    """Представление запроса на сброс пароля."""

    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'reset_password_request'

    def post(self, request, *args, **kwargs):
        """Генерирует ссылку восстановления и логирует ее."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        user = User.objects.filter(email=email).first()

        response_data = {
            'detail': (
                'Если учетная запись с таким email существует, '
                'инструкция по восстановлению будет на него отправлена.'
            ),
        }

        if user:
            frontend_base_url = settings.FRONTEND_RESET_PASSWORD_URL
            reset_url = build_password_reset_url(user, frontend_base_url)

            if settings.DEBUG:
                response_data['debug_reset_url'] = reset_url
            return Response(
                response_data,
                status=status.HTTP_200_OK,
            )
        logger.info(
            'Попытка сброса пароля для несуществующего email: %s',
            email,
        )
        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )


@password_reset_verify_schema
class PasswordResetVerifyView(GenericAPIView):
    """Представление подтверждения токена для восстановления пароля."""

    permission_classes = [AllowAny]
    serializer_class = PasswordResetVerifySerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'reset_password_verify'

    def post(self, request, *args, **kwargs):
        """Проверяет uid и токен восстановления."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(
            {
                'detail': 'Ссылка действительна.',
            },
            status=status.HTTP_200_OK,
        )


@password_reset_confirm_schema
class PasswordResetConfirmView(GenericAPIView):
    """Представление установки нового пароля."""

    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'reset_password_confirm'

    def post(self, request, *args, **kwargs):
        """Проверяет данные и устанавливает новый пароль."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                'detail': 'Новый пароль сохранен.',
            },
            status=status.HTTP_200_OK,
        )


@change_username_schema
class UsernameChangeView(UpdateAPIView):
    """Представление изменения username."""

    serializer_class = UsernameChangeSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['patch']
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'change_username'

    def get_object(self):
        return self.request.user
