from django.urls import path

from users.views import SocialLoginView

urlpatterns = [
    path('get_tokens/', SocialLoginView.as_view(), name='social_login'),
]
