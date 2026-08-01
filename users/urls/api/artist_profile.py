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
    ManagedArtistCoverUpdateView,
    ManagedArtistPickupPointViewSet,
    ManagedArtistProfileView,
    ManagedArtistShippingPointView,
    RecipientTypeListView,
    TelegramConnectView,
)

me_pickup_point_list = ArtistPickupPointViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

me_pickup_point_detail = ArtistPickupPointViewSet.as_view({
    'get': 'retrieve',
    'patch': 'partial_update',
    'delete': 'destroy',
})

managed_pickup_point_list = ManagedArtistPickupPointViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

managed_pickup_point_detail = ManagedArtistPickupPointViewSet.as_view({
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
        me_pickup_point_list,
        name='artist_me_pickup_point_list',
    ),
    path(
        'me/pickup-points/<int:pk>/',
        me_pickup_point_detail,
        name='artist_me_pickup_point_detail',
    ),
    path(
        'me/shipping-point/',
        ArtistShippingPointView.as_view(),
        name='artist_me_shipping_point',
    ),
    path(
        'me/managed-profiles/',
        LabelManagedProfileListView.as_view(),
        name='label_managed_profiles',
    ),
    path(
        'me/managed-profiles/<int:profile_id>/',
        ManagedArtistProfileView.as_view(),
        name='managed_profile_detail',
    ),
    path(
        'me/managed-profiles/<int:profile_id>/pickup-points/',
        managed_pickup_point_list,
        name='managed_profile_pickup_point_list',
    ),
    path(
        'me/managed-profiles/<int:profile_id>/pickup-points/<int:pk>/',
        managed_pickup_point_detail,
        name='managed_profile_pickup_point_detail',
    ),
    path(
        'me/managed-profiles/<int:profile_id>/shipping-point/',
        ManagedArtistShippingPointView.as_view(),
        name='managed_profile_shipping_point',
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
        'me/managed-profiles/<int:profile_id>/cover/',
        ManagedArtistCoverUpdateView.as_view(),
        name='managed_artist_cover_update',
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
