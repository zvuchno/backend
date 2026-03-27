"""Представления для управления учетной записью пользователя."""

import logging

from django.conf import settings
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
    email_verification_schema,
    me_schema,
    resend_verification_email_schema,
)
from users.serializers import (
    ChangePasswordSerializer,
    EmailVerificationSerializer,
    MeSerializer,
)
from users.serializers.account import EmptySerializer, PhoneChangeSerializer
from users.services import build_email_verification_url

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

        logger.info(
            'Email verification link for %s: %s',
            user.email,
            verification_url,
        )

        return Response(
            {'detail': 'Запрос на подтверждение Email принят.'},
            status=status.HTTP_200_OK,
        )
