"""URL-маршруты профиля слушателя."""

from django.urls import path

from users.views import ListenerMeView

urlpatterns = [path('me/', ListenerMeView.as_view(), name='listener_me')]
