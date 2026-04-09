"""OpenAPI схемы для API приложения users."""

from .account import (
    change_password_schema,
    change_phone_schema,
    email_verification_schema,
    me_schema,
    password_reset_confirm_schema,
    password_reset_request_schema,
    password_reset_verify_schema,
    resend_verification_email_schema,
)
from .artist_profile import (
    artist_cover_update_schema,
    artist_list_schema,
    artist_me_schema,
    artist_public_schema,
    become_artist_schema,
)
from .auth import (
    logout_schema,
    token_obtain_schema,
    token_refresh_schema,
    token_verify_schema,
)
from .listener_profile import listener_me_schema
from .registration import (
    artist_registration_schema,
    listener_registration_schema,
)
from .social_auth import social_token_exchange_schema

__all__ = [
    'artist_cover_update_schema',
    'artist_list_schema',
    'artist_me_schema',
    'artist_public_schema',
    'artist_registration_schema',
    'become_artist_schema',
    'change_password_schema',
    'change_phone_schema',
    'email_verification_schema',
    'listener_me_schema',
    'listener_registration_schema',
    'logout_schema',
    'me_schema',
    'password_reset_confirm_schema',
    'password_reset_request_schema',
    'password_reset_verify_schema',
    'resend_verification_email_schema',
    'token_obtain_schema',
    'token_refresh_schema',
    'token_verify_schema',
    'social_token_exchange_schema',
]
