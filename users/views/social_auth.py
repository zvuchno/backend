"""Представления для входа через сторонние сервисы."""

from django.contrib.auth import logout
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from users.schemas import (
    social_token_exchange_schema,
)
from users.services import issue_tokens_for_user


@social_token_exchange_schema
class SocialLoginView(GenericAPIView):
    """Вход или регистрация через соцсеть."""

    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tokens = issue_tokens_for_user(request.user)
        logout(request)
        return Response(tokens)
