from .account import (
    ChangePasswordView,
    ChangePhoneView,
    EmailVerificationView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    ResendVerificationEmailView,
    SetPasswordView,
)
from .artist_delivery import (
    ArtistPickupPointViewSet,
    ArtistShippingPointView,
    ManagedArtistPickupPointViewSet,
    ManagedArtistShippingPointView,
)
from .artist_legal_profile import (
    ArtistLegalProfileView,
    RecipientTypeListView,
)
from .artist_profile import (
    ArtistCoverUpdateView,
    ArtistListView,
    ArtistMeView,
    ArtistPublicView,
    BecomeArtistOrLabelView,
    LabelManagedProfileListView,
    ManagedArtistCoverUpdateView,
    ManagedArtistProfileView,
)
from .artist_registration import ArtistRegistrationView
from .artist_store_settings import (
    ArtistStoreSettingsView,
    ManagedArtistStoreSettingsView,
)
from .base_registration import BaseRegistrationView
from .consent_documents import ConsentDocumentViewSet
from .cookie_auth import (
    CookieLoginView,
    CookieLogoutView,
    CookieRefreshView,
)
from .invitation import (
    ArtistProfileClaimInvitationAcceptView,
    ArtistProfileClaimInvitationCreateView,
    ArtistProfileClaimInvitationRejectView,
    ArtistProfileClaimInvitationResendView,
    ArtistProfileClaimInvitationRevokeView,
    ArtistProfileClaimInvitationView,
)
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
    redirect_social_auth_cancelled,
    redirect_social_auth_confirm_email,
    redirect_social_auth_error,
    redirect_social_auth_signup,
)
from .telegram_connect import TelegramConnectView

__all__ = [
    'ArtistCoverUpdateView',
    'ArtistLegalProfileView',
    'ArtistListView',
    'ArtistMeView',
    'ArtistPickupPointViewSet',
    'ArtistProfileClaimInvitationAcceptView',
    'ArtistProfileClaimInvitationCreateView',
    'ArtistProfileClaimInvitationResendView',
    'ArtistProfileClaimInvitationRejectView',
    'ArtistProfileClaimInvitationRevokeView',
    'ArtistProfileClaimInvitationView',
    'ArtistPublicView',
    'ArtistRegistrationView',
    'ArtistShippingPointView',
    'ArtistStoreSettingsView',
    'BaseRegistrationView',
    'BecomeArtistOrLabelView',
    'ConsentDocumentViewSet',
    'ChangePasswordView',
    'ChangePhoneView',
    'CookieLoginView',
    'CookieLogoutView',
    'CookieRefreshView',
    'CustomLogoutView',
    'CustomTokenObtainPairView',
    'CustomTokenRefreshView',
    'CustomTokenVerifyView',
    'EmailVerificationView',
    'LabelManagedProfileListView',
    'ListenerMeView',
    'ListenerRegistrationView',
    'ManagedArtistCoverUpdateView',
    'ManagedArtistPickupPointViewSet',
    'ManagedArtistProfileView',
    'ManagedArtistShippingPointView',
    'ManagedArtistStoreSettingsView',
    'MeView',
    'PasswordResetConfirmView',
    'PasswordResetRequestView',
    'PasswordResetVerifyView',
    'RecipientTypeListView',
    'ResendVerificationEmailView',
    'redirect_social_auth_cancelled',
    'redirect_social_auth_confirm_email',
    'redirect_social_auth_error',
    'redirect_social_auth_signup',
    'SetPasswordView',
    'SocialAuthErrorCodesView',
    'TelegramConnectView',
    'VKLogin',
    'YandexLogin',
]
