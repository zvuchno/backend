"""
URL-конфигурация приложения `store`.

Определяет маршруты для API с использованием DRF DefaultRouter.

Все маршруты автоматически получают стандартные CRUD-эндпойнты:
list, retrieve, create, update, partial_update, destroy.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AlbumViewSet, GenreViewSet, TrackViewSet

app_name = 'store'

router = DefaultRouter()
router.register(r'genres', GenreViewSet, basename='genres')
router.register(r'albums', AlbumViewSet, basename='albums')
router.register(r'track', TrackViewSet, basename='track')

urlpatterns = [
    path('', include(router.urls)),
]
