"""URL-конфигурация приложения `store`.

Определяет маршруты для API с использованием DRF DefaultRouter.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AlbumViewSet,
    CartViewSet,
    DeliveryViewSet,
    GenreViewSet,
    OrderViewSet,
    TrackViewSet,
)

app_name = 'store'

router = DefaultRouter()
router.register(r'genres', GenreViewSet, basename='genres')
router.register(r'albums', AlbumViewSet, basename='albums')
router.register(r'tracks', TrackViewSet, basename='tracks')
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'deliveries', DeliveryViewSet, basename='deliveries')
router.register(r'orders', OrderViewSet, basename='orders')

urlpatterns = [
    path('', include(router.urls)),
]
