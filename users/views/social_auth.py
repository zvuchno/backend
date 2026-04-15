"""Представления для входа через сторонние сервисы."""

from django.contrib.auth import logout
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
