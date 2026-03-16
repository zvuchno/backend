"""URL-маршруты регистрации пользователей.

Модуль содержит маршруты для регистрации
пользователей разных ролей.
"""

from django.urls import path

from users.views import (
    ArtistRegistrationView,
    ListenerRegistrationView,
)

urlpatterns = [
    path(
        'listener/',
        ListenerRegistrationView.as_view(),
        name='listener_registration',
    ),
    path(
        'artist/',
        ArtistRegistrationView.as_view(),
        name='artist_registration',
    ),
]
