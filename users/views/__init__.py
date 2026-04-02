from .account import (
    ChangePasswordView,
    ChangePhoneView,
    EmailVerificationView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
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
from .listener_profile import ListenerMeView
from .listener_registration import ListenerRegistrationView
from .social_auth import (
    SocialCompleteSignupView,
    SocialVkLoginView,
)

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
    'ListenerMeView',
    'ListenerRegistrationView',
    'MeView',
    'ChangePhoneView',
    'ChangePasswordView',
    'EmailVerificationView',
    'PasswordResetConfirmView',
    'PasswordResetRequestView',
    'PasswordResetVerifyView',
    'ResendVerificationEmailView',
    'SocialCompleteSignupView',
    'SocialVkLoginView',
]
