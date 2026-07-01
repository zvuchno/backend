"""URL-маршруты для управления учетной записью."""

from django.urls import path

from users.views import (
    BecomeArtistView,
    ChangePasswordView,
    ChangePhoneView,
    EmailVerificationView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    ResendVerificationEmailView,
)
from users.views.account import (
    SetPasswordView,
    UsernameChangeView,
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
        'me/become_artist/',
        BecomeArtistView.as_view(),
        name='become_artist',
    ),
    path(
        'verify-email/',
        EmailVerificationView.as_view(),
        name='verify_email',
    ),
    path(
        'me/set-password/',
        SetPasswordView.as_view(),
        name='set_password',
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
    path(
        'me/change-username/',
        UsernameChangeView.as_view(),
        name='change_username',
    ),
]
