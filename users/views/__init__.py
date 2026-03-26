from .account import (
    ChangePasswordView,
    ChangePhoneView,
    EmailVerificationView,
    MeView,
    ResendVerificationEmailView,
)
from .artist_profile import (
    ArtistCoverUpdateView,
    ArtistListView,
    ArtistMeView,
    ArtistPublicView,
)
from .artist_registration import ArtistRegistrationView
from .base_registration import BaseRegistrationView
from .jwt import (
    CustomLogoutView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    CustomTokenVerifyView,
)
from .listener_registration import ListenerRegistrationView

__all__ = [
    'ArtistCoverUpdateView',
    'ArtistListView',
    'ArtistMeView',
    'ArtistPublicView',
    'ArtistRegistrationView',
    'BaseRegistrationView',
    'CustomLogoutView',
    'CustomTokenObtainPairView',
    'CustomTokenRefreshView',
    'CustomTokenVerifyView',
    'ListenerRegistrationView',
    'MeView',
    'ChangePhoneView',
    'ChangePasswordView',
    'EmailVerificationView',
    'ResendVerificationEmailView',
]
