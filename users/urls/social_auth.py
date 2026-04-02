from django.urls import path

from users.views import (
    SocialCompleteSignupView,
    SocialVkLoginView,
)

urlpatterns = [
    path('vk/', SocialVkLoginView.as_view(), name='social_vk_login'),
    path(
        'complete-signup/',
        SocialCompleteSignupView.as_view(),
        name='social_complete_signup',
    ),
]
