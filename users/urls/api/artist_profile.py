"""URL-маршруты профиля артиста."""

from django.urls import path

from store.views import ArtistSaleViewSet
from users.views import (
    ArtistCoverUpdateView,
    ArtistLegalProfileView,
    ArtistListView,
    ArtistMeView,
    ArtistPickupPointViewSet,
    ArtistPublicView,
    ArtistShippingPointView,
    LabelManagedProfileListView,
    RecipientTypeListView,
    TelegramConnectView,
)

managed_pickup_point_list = ArtistPickupPointViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

managed_pickup_point_detail = ArtistPickupPointViewSet.as_view({
    'get': 'retrieve',
    'patch': 'partial_update',
    'delete': 'destroy',
})

urlpatterns = [
    path(
        'me/',
        ArtistMeView.as_view(),
        name='artist_me',
    ),
    path(
        'me/pickup-points/',
        managed_pickup_point_list,
        name='artist-me-pickup-point-list',
    ),
    path(
        'me/pickup-points/<int:pk>/',
        managed_pickup_point_detail,
        name='artist-me-pickup-point-detail',
    ),
    path(
        'me/shipping-point/',
        ArtistShippingPointView.as_view(),
        name='artist-me-shipping-point',
    ),
    path(
        'me/managed-profiles/',
        LabelManagedProfileListView.as_view(),
        name='label-managed-profiles',
    ),
    path(
        'me/managed-profiles/<int:profile_id>/pickup-points/',
        managed_pickup_point_list,
        name='managed-profile-pickup-point-list',
    ),
    path(
        'me/managed-profiles/<int:profile_id>/pickup-points/<int:pk>/',
        managed_pickup_point_detail,
        name='managed-profile-pickup-point-detail',
    ),
    path(
        'me/managed-profiles/<int:profile_id>/shipping-point/',
        ArtistShippingPointView.as_view(),
        name='managed-profile-shipping-point',
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
        'artists/me/managed-profiles/<int:profile_id>/cover/',
        ArtistCoverUpdateView.as_view(),
        name='managed-artist-cover-update',
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
