"""URL-маршруты аутентификации.

Модуль содержит маршруты для аутентификации пользователей.
"""

from dj_rest_auth.jwt_auth import get_refresh_view
from dj_rest_auth.views import LogoutView
from django.urls import path

from users.views import (
    CustomLogoutView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    CustomTokenVerifyView,
    SessionLoginView,
    SocialAuthErrorCodesView,
    VKLogin,
    YandexLogin,
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
    path(
        'session/login/',
        SessionLoginView.as_view(),
        name='session_login',
    ),
    path(
        'session/refresh/',
        get_refresh_view().as_view(),
        name='session_refresh',
    ),
    path(
        'session/logout/',
        LogoutView.as_view(),
        name='session_logout',
    ),
    path(
        'social/error-codes/',
        SocialAuthErrorCodesView.as_view(),
        name='social_error_codes',
    ),
    path('social/vk/', VKLogin.as_view(), name='vk_login'),
    path('social/yandex/', YandexLogin.as_view(), name='yandex_login'),
]
