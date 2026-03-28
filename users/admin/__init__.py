from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from . import artist as artist
from . import listener as listener
from . import user as user

# Убираем Token Blacklist
for model in (OutstandingToken, BlacklistedToken):
    try:
        admin.site.unregister(model)
    except NotRegistered:
        pass
