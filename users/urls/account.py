"""URL-маршруты для управления учетной записью."""

from django.urls import path

from users.views import (
    ChangePasswordView,
    ChangePhoneView,
    EmailVerificationView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
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
        'me/change-phone/',
        ChangePhoneView.as_view(),
        name='change_phone',
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
    path(
        'reset-password/',
        PasswordResetRequestView.as_view(),
        name='reset_password',
    ),
    path(
        'reset-password-verify/',
        PasswordResetVerifyView.as_view(),
        name='reset_password_verify',
    ),
    path(
        'reset-password-confirm/',
        PasswordResetConfirmView.as_view(),
        name='reset_password_confirm',
    ),
]
