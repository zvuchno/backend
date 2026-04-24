"""URL-маршруты профиля артиста."""

from django.urls import path

from users.views import (
    ArtistCoverUpdateView,
    ArtistLegalProfileView,
    ArtistListView,
    ArtistMeView,
    ArtistPublicView,
)

urlpatterns = [
    path(
        'me/',
        ArtistMeView.as_view(),
        name='artist_me',
    ),
    path(
        'legal/me/',
        ArtistLegalProfileView.as_view(),
        name='artist_legal_profile',
    ),
    path(
        'me/cover/',
        ArtistCoverUpdateView.as_view(),
        name='artist_cover_update',
    ),
    path(
        '',
        ArtistListView.as_view(),
        name='artist_list',
    ),
    path(
        'profile/<slug:slug>/',
        ArtistPublicView.as_view(),
        name='artist_public',
    ),
]
