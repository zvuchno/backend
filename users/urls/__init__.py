"""Корневые URL-маршруты приложения users."""

from django.urls import include, path

app_name = 'users'

urlpatterns = [
    path('auth/token/', include('users.urls.auth')),
    path('auth/register/', include('users.urls.registration')),
    path('auth/account/', include('users.urls.account')),
    path('listener/', include('users.urls.listener_profile')),
    path('artists/', include('users.urls.artist_profile')),
]
