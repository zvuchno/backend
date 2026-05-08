"""Корневые URL-маршруты приложения users."""

from django.urls import include, path

app_name = 'users'

urlpatterns = [
    path('auth/', include('users.urls.api.auth')),
    path('auth/register/', include('users.urls.api.registration')),
    path('auth/account/', include('users.urls.api.account')),
    path('listener/', include('users.urls.api.listener_profile')),
    path('artists/', include('users.urls.api.artist_profile')),
    path('compliance/', include('users.urls.api.compliance')),
]
