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
from .artist_legal_profile import ArtistLegalProfileView
from .artist_profile import (
    ArtistCoverUpdateView,
    ArtistListView,
    ArtistMeView,
    ArtistPublicView,
    BecomeArtistView,
)
from .artist_registration import ArtistRegistrationView
from .base_registration import BaseRegistrationView
from .consent_documents import ConsentDocumentViewSet
from .jwt import (
    CustomLogoutView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    CustomTokenVerifyView,
    VKLogin,
    YandexLogin,
)
from .listener_profile import ListenerMeView
from .listener_registration import ListenerRegistrationView
from .social_auth import (
    SocialAuthErrorCodesView,
    SocialSessionExchangeView,
    redirect_social_auth_cancelled,
    redirect_social_auth_confirm_email,
    redirect_social_auth_error,
    redirect_social_auth_signup,
)

__all__ = [
    'ArtistCoverUpdateView',
    'ArtistListView',
    'ArtistMeView',
    'ArtistPublicView',
    'ArtistRegistrationView',
    'BecomeArtistView',
    'BaseRegistrationView',
    'ConsentDocumentViewSet',
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
    'redirect_social_auth_cancelled',
    'redirect_social_auth_error',
    'redirect_social_auth_signup',
    'redirect_social_auth_confirm_email',
    'ResendVerificationEmailView',
    'SocialAuthErrorCodesView',
    'ArtistLegalProfileView',
    'SocialSessionExchangeView',
    'VKLogin',
    'YandexLogin',
]
