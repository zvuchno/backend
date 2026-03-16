"""Корневые URL-маршруты приложения users."""

from django.urls import include, path

app_name = 'users'

urlpatterns = [
    path('token/', include('users.urls.auth')),
    path('register/', include('users.urls.registration')),
]
