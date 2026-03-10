from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AlbumViewSet, GenreViewSet

app_name = 'store'

router = DefaultRouter()
router.register(r'genres', GenreViewSet, basename='genres')
router.register(r'albums', AlbumViewSet, basename='albums')

urlpatterns = [
    path('', include(router.urls)),
]
