"""Представления профиля слушателя."""

from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from users.models import ListenerProfile
from users.serializers.listener_profile import ListenerMeSerializer


@extend_schema(tags=['Profile: listener'])
class ListenerMeView(RetrieveUpdateAPIView):
    """Просмотр и редактирование профиля текущего слушателя."""

    permission_classes = [IsAuthenticated]
    serializer_class = ListenerMeSerializer
    http_method_names = ['get', 'patch']

    def get_object(self):
        """Возвращает профиль текущего слушателя."""
        try:
            return ListenerProfile.objects.select_related('user').get(
                user=self.request.user,
            )
        except ListenerProfile.DoesNotExist:
            raise Http404('Профиль слушателя не найден.')
