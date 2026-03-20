"""URL-маршруты для управления учетной записью."""

from django.urls import path

from users.views import (
    ChangePasswordView,
    EmailVerificationView,
    MeView,
    ResendVerificationEmailView,
)

urlpatterns = [
    path('me/', MeView.as_view(), name='me'),
    path(
        'me/change-password/',
        ChangePasswordView.as_view(),
        name='change_password',
    ),
    path(
        'me/resend-email/',
        ResendVerificationEmailView.as_view(),
        name='resend_verification_email',
    ),
    path(
        'verify-email/',
        EmailVerificationView.as_view(),
        name='verify_email',
    ),
]
