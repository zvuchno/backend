"""URL-конфигурация приложения `store`.

Определяет маршруты для API с использованием DRF DefaultRouter.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AlbumViewSet,
    CDEKWidgetView,
    CartViewSet,
    CatalogMerchDetailView,
    CatalogReleaseDetailView,
    CreatePaymentView,
    DeliveryViewSet,
    FavoritesViewSet,
    GenreViewSet,
    MerchKindViewSet,
    MerchViewSet,
    OrderViewSet,
    ProductCatalogListView,
    PromocodeViewSet,
    PurchasedMusicArchiveDownloadLinkView,
    PurchasedMusicDLDetailView,
    PurchasedMusicTrackDownloadLinkView,
    PurchasedMusicView,
    TrackViewSet,
    yookassa_webhook,
)

app_name = 'store'

router = DefaultRouter()
router.register(r'genres', GenreViewSet, basename='genres')
router.register(r'albums', AlbumViewSet, basename='albums')
router.register(r'merch-kinds', MerchKindViewSet, basename='merch-kinds')
router.register(r'merch', MerchViewSet, basename='merch')
router.register(r'tracks', TrackViewSet, basename='tracks')
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'deliveries', DeliveryViewSet, basename='deliveries')
router.register(r'me/favorites', FavoritesViewSet, basename='me-favorites')
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'promocodes', PromocodeViewSet, basename='promocodes')

urlpatterns = [
    path('', include(router.urls)),
    path('catalog/', ProductCatalogListView.as_view(), name='catalog'),
    path(
        'catalog/release/<int:pk>/',
        CatalogReleaseDetailView.as_view({'get': 'retrieve'}),
        name='catalog-release-detail',
    ),
    path(
        'catalog/merch/<int:pk>/',
        CatalogMerchDetailView.as_view({'get': 'retrieve'}),
        name='catalog-merch-detail',
    ),
    path(
        'me/purchased-music',
        PurchasedMusicView.as_view(),
        name='purchased-music',
    ),
    path(
        'me/purchased-music/<int:album_id>/',
        PurchasedMusicDLDetailView.as_view(),
        name='purchased-music-download-detail',
    ),
    path(
        'me/purchased-music/download-link/track/<int:track_id>/',
        PurchasedMusicTrackDownloadLinkView.as_view(),
        name='purchased-music-track-download-link',
    ),
    path(
        'me/purchased-music/download-link/album-archive/<int:album_id>/',
        PurchasedMusicArchiveDownloadLinkView.as_view(),
        name='purchased-music-archive-download-link',
    ),
    path('cdek/widget', CDEKWidgetView.as_view(), name='cdek-widget'),
    path(
        'payments/create/',
        CreatePaymentView.as_view(),
        name='payment-create',
    ),
    path('payments/webhook/', yookassa_webhook, name='payment-webhook'),
]
