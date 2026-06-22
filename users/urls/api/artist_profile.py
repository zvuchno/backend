"""URL-маршруты профиля артиста."""

from django.urls import path

from store.views import ArtistSaleViewSet
from users.views import (
    ArtistCoverUpdateView,
    ArtistLegalProfileView,
    ArtistListView,
    ArtistMeView,
    ArtistPublicView,
    RecipientTypeListView,
    TelegramConnectView,
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
        'me/legal/recipient-types/',
        RecipientTypeListView.as_view(),
        name='recipient_type_list',
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
    path(
        'me/telegram/connect/',
        TelegramConnectView.as_view(),
        name='artist_telegram_connect',
    ),
]
