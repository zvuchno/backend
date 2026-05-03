"""URL-маршруты профиля артиста."""

from django.urls import path

from store.views import ArtistSaleViewSet
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
        'me/legal/',
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
    path(
        'me/sales/',
        ArtistSaleViewSet.as_view({'get': 'list'}),
        name='artist_sales',
    ),
    path(
        'me/sales/<int:pk>/',
        ArtistSaleViewSet.as_view({'get': 'retrieve'}),
        name='artist_sale_detail',
    ),
]
