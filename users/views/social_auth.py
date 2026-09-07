"""Представления для входа через сторонние сервисы."""

from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from rest_framework.permissions import (
    AllowAny,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from common.utils.urls import build_frontend_url

from config import settings
from users.constants import SOCIAL_AUTH_ERRORS
from users.schemas import (
    social_error_codes_schema,
)
from users.serializers import (
    EmptySerializer,
)


def _redirect_social_auth_to_frontend(status, **extra) -> HttpResponseRedirect:
    """Редирект на указанную страницу фронта."""
    target_url = build_frontend_url(
        settings.FRONTEND_SOCIAL_AUTH_PATH,
        {
            'status': status,
            **extra,
        },
    )
    return redirect(target_url)


def redirect_social_auth_cancelled(request):
    """Редирект при отмене social auth."""
    return _redirect_social_auth_to_frontend('cancelled')


def redirect_social_auth_error(request):
    """Редирект при ошибке social auth."""
    return _redirect_social_auth_to_frontend('error')


def redirect_social_auth_signup(request):
    """Редирект fallback signup social auth на фронт."""
    return _redirect_social_auth_to_frontend('signup')


def redirect_social_auth_confirm_email(request):
    """Редирект fallback confirm-email social auth на фронт."""
    return _redirect_social_auth_to_frontend('confirm-email')


@social_error_codes_schema
class SocialAuthErrorCodesView(APIView):
    """Справочник кодов ошибок social auth."""

    permission_classes = (AllowAny,)
    serializer_class = EmptySerializer

    def get(self, request):
        return Response(SOCIAL_AUTH_ERRORS)
