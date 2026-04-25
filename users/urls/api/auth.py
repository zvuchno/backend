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
    SocialSessionExchangeView,
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
        'social/get_tokens/',
        SocialSessionExchangeView.as_view(),
        name='social_login',
    ),
    path(
        'social/error-codes/',
        SocialAuthErrorCodesView.as_view(),
        name='social_error_codes',
    ),
    path('social/vk/', VKLogin.as_view(), name='vk_login'),
    path('social/yandex/', YandexLogin.as_view(), name='yandex_login'),
]
