"""URL-маршруты аутентификации.

Модуль содержит маршруты для аутентификации пользователей.
"""

from django.urls import path

from users.views import (
    CookieLoginView,
    CookieLogoutView,
    CookieRefreshView,
    CustomLogoutView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    CustomTokenVerifyView,
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
    path(
        'token/logout/',
        CustomLogoutView.as_view(),
        name='token_logout',
    ),
    path(
        'token/verify/',
        CustomTokenVerifyView.as_view(),
        name='token_verify',
    ),
    path(
        'cookie/login/',
        CookieLoginView.as_view(),
        name='cookie_login',
    ),
    path(
        'cookie/refresh/',
        CookieRefreshView.as_view(),
        name='cookie_refresh',
    ),
    path(
        'cookie/logout/',
        CookieLogoutView.as_view(),
        name='cookie_logout',
    ),
    path(
        'social/error-codes/',
        SocialAuthErrorCodesView.as_view(),
        name='social_error_codes',
    ),
    path('social/vk/', VKLogin.as_view(), name='vk_login'),
    path('social/yandex/', YandexLogin.as_view(), name='yandex_login'),
]
