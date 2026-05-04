"""URL-маршруты юридических документов и пользовательских согласий."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from users.views import ConsentDocumentViewSet

router = DefaultRouter()

router.register(
    r'consent-documents',
    ConsentDocumentViewSet,
    basename='consent-document',
)

urlpatterns = [
    path('', include(router.urls)),
]
