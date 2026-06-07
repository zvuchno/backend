"""URL-конфигурация приложения `store`.

Определяет маршруты для API с использованием DRF DefaultRouter.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AlbumViewSet,
    CartViewSet,
    CatalogMerchDetailView,
    CatalogReleaseDetailView,
    DeliveryViewSet,
    FavoritesViewSet,
    GenreViewSet,
    MerchKindViewSet,
    MerchViewSet,
    OrderViewSet,
    ProductCatalogListView,
    PromocodeViewSet,
    TrackViewSet,
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
        CatalogReleaseDetailView.as_view(),
        name='catalog-release-detail',
    ),
    path(
        'catalog/merch/<int:pk>/',
        CatalogMerchDetailView.as_view(),
        name='catalog-merch-detail',
    ),
]
