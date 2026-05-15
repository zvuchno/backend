from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialToken
from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from . import artist as artist
from . import artist_legal_profile as artist_legal_profile
from . import consent_document as consent_document
from . import listener as listener
from . import user as user
from . import user_consent as user_consent

# Убираем Token Blacklist и лишнее от allauth
for model in (
    OutstandingToken,
    BlacklistedToken,
    EmailAddress,
    SocialToken,
):
    try:
        admin.site.unregister(model)
    except NotRegistered:
        pass
