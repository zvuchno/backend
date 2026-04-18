from allauth.socialaccount import providers
from django.urls import include, path

from users.views import (
    SocialAuthErrorCodesView,
    redirect_social_auth_cancelled,
    redirect_social_auth_confirm_email,
    redirect_social_auth_error,
    redirect_social_auth_signup,
)

urlpatterns = [
    *[
        path(
            '',
            include(f'allauth.socialaccount.providers.{provider.id}.urls'),
        )
        for provider in providers.registry.get_class_list()
    ],
    path(
        'social/login/cancelled/',
        redirect_social_auth_cancelled,
        name='account_login_cancelled',
    ),
    path(
        'social/login/error/',
        redirect_social_auth_error,
        name='account_login_error',
    ),
    path(
        'social/signup/',
        redirect_social_auth_signup,
        name='account_signup',
    ),
    # Fallback заглушка для allauth.
    path(
        '',
        redirect_social_auth_confirm_email,
        name='account_confirm_email',
    ),
    path(
        'social/error-codes/',
        SocialAuthErrorCodesView.as_view(),
        name='social_error_codes',
    ),
]
