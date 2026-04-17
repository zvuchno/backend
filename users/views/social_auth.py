"""Представления для входа через сторонние сервисы."""

from urllib.parse import urlencode

from django.contrib.auth import logout
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config import settings
from users.helpers import (
    issue_tokens_for_user,
    run_actions_after_authentication,
)
from users.schemas import (
    social_token_exchange_schema,
)
from users.serializers import TokenPairSerializer


@social_token_exchange_schema
class SocialLoginView(GenericAPIView):
    """Вход или регистрация через соцсеть."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = TokenPairSerializer

    def post(self, request):
        user = request.user

        run_actions_after_authentication(user, request)

        tokens = issue_tokens_for_user(user)
        logout(request)
        response = Response(tokens)
        response['Cache-Control'] = (
            'no-store, no-cache, must-revalidate, private'
        )
        response['Pragma'] = 'no-cache'
        return response


def _redirect_social_auth_to_frontend(status, **extra) -> HttpResponseRedirect:
    """Редирект на указанную страницу фронта."""
    target_url = getattr(settings, 'FRONTEND_SOCIAL_AUTH_URL', '/')
    query = urlencode({
        'status': status,
        **extra,
    })
    return redirect(f'{target_url}?{query}')


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
