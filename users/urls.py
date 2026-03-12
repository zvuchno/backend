"""URL-маршруты приложения users.

Модуль содержит маршруты для аутентификации,
получения JWT-токенов и регистрации пользователей
разных ролей.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from users.views import ArtistRegistrationView, ListenerRegistrationView


router = DefaultRouter()

urlpatterns = [
    path('register/listener/', ListenerRegistrationView.as_view()),
    path('register/artist/', ArtistRegistrationView.as_view()),
]
