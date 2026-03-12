from django.urls import include, path
from rest_framework.routers import DefaultRouter

from store.views import AlbumViewSet, GenreViewSet, MerchViewSet

app_name = 'store'

router = DefaultRouter()
router.register(r'genres', GenreViewSet, basename='genres')
router.register(r'albums', AlbumViewSet, basename='albums')
router.register(r'merch', MerchViewSet, basename='merch')

urlpatterns = [
    path('', include(router.urls)),
]
