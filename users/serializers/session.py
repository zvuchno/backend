from dj_rest_auth.serializers import LoginSerializer
from rest_framework import serializers

from users.helpers import run_actions_after_authentication


class SessionLoginSerializer(LoginSerializer):
    """Сериализатор входа в cookie-сессию."""

    username = None
    email = serializers.EmailField(required=True)

    def validate(self, attrs):
        attrs['username'] = attrs.get('email')

        validated_data = super().validate(attrs)

        run_actions_after_authentication(
            validated_data['user'],
            self.context['request'],
        )

        return validated_data
