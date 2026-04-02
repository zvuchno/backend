from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from users.schemas.social_auth import (
    social_complete_signup_schema,
    social_signup_schema,
)
from users.serializers.social_auth import (
    SocialCompleteSignupSerializer,
    SocialVkLoginSerializer,
)
from users.services.social_auth import (
    complete_social_signup,
    login_with_vk,
)


@social_signup_schema
class SocialVkLoginView(GenericAPIView):
    """Вход или регистрация через VK."""

    permission_classes = [AllowAny]
    serializer_class = SocialVkLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = login_with_vk(
            code=serializer.validated_data['code'],
            redirect_uri=serializer.validated_data['redirect_uri'],
        )
        return Response(result, status=status.HTTP_200_OK)


@social_complete_signup_schema
class SocialCompleteSignupView(GenericAPIView):
    """Завершение соц регистрации после дозаполнения email."""

    permission_classes = [AllowAny]
    serializer_class = SocialCompleteSignupSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = complete_social_signup(
            signup_token=serializer.validated_data['signup_token'],
            email=serializer.validated_data['email'],
        )
        return Response(result, status=status.HTTP_200_OK)
