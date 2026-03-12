"""URL-маршруты аутентификации.

Модуль содержит маршруты для аутентификации пользователей.
"""

from django.urls import path

from users.views import (
    CustomLogoutView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    CustomTokenVerifyView,
)

urlpatterns = [
    path('create/', CustomTokenObtainPairView.as_view(), name='token_create'),
    path('refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', CustomLogoutView.as_view(), name='token_logout'),
    path('verify/', CustomTokenVerifyView.as_view(), name='token_verify'),
]
