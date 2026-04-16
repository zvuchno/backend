from allauth.socialaccount import providers
from django.urls import include, path

from users.views import (
    redirect_social_auth_cancelled,
    redirect_social_auth_error,
    redirect_social_auth_signup,
)

app_name = 'oauth'

urlpatterns = [
    *[
        path(
            f'{provider.id}/',
            include(f'allauth.socialaccount.providers.{provider.id}.urls'),
        )
        for provider in providers.registry.get_class_list()
    ],
    path(
        'social/login/cancelled/',
        redirect_social_auth_cancelled,
        name='socialaccount_login_cancelled',
    ),
    path(
        'social/login/error/',
        redirect_social_auth_error,
        name='socialaccount_login_error',
    ),
    path(
        'social/signup/',
        redirect_social_auth_signup,
        name='socialaccount_signup',
    ),
]
