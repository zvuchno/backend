"""URL-маршруты приложения users.

Модуль содержит маршруты для аутентификации,
получения JWT-токенов и регистрации пользователей
разных ролей.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from users.views import ArtistRegistrationView, ListenerRegistrationView


router = DefaultRouter()

urlpatterns = [
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
    path('auth/register/listener/', ListenerRegistrationView.as_view()),
    path('auth/register/artist/', ArtistRegistrationView.as_view()),
]
