"""URL-маршруты аутентификации.

Модуль содержит маршруты для аутентификации пользователей.
"""

from django.urls import path

from users.views import (
    CustomLogoutView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    CustomTokenVerifyView,
    SocialAuthErrorCodesView,
    SocialLoginView,
)

urlpatterns = [
    path(
        'token/create/',
        CustomTokenObtainPairView.as_view(),
        name='token_create',
    ),
    path(
        'token/refresh/',
        CustomTokenRefreshView.as_view(),
        name='token_refresh',
    ),
    path('token/logout/', CustomLogoutView.as_view(), name='token_logout'),
    path(
        'token/verify/',
        CustomTokenVerifyView.as_view(),
        name='token_verify',
    ),
    path('social/get_tokens/', SocialLoginView.as_view(), name='social_login'),
    path(
        'social/error-codes/',
        SocialAuthErrorCodesView.as_view(),
        name='social_error_codes',
    ),
]
