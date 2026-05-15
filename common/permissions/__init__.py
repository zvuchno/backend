"""Публичные пермишены проекта.

Экспортирует готовые к использованию классы пермишенов для:
- ролевого доступа;
- доступа по владельцу объекта;
- проверки подтверждённого аккаунта.
"""

from .ownership import (
    IsSalesOwner,
    IsStoreObjectOwner,
    IsStoreObjectOwnerOrReadOnly,
    IsUserObjectOwner,
    IsUserObjectOwnerOrReadOnly,
)
from .profiles import IsArtist, IsListener, IsNotArtist
from .verification import IsUserVerified

__all__ = [
    'IsArtist',
    'IsListener',
    'IsNotArtist',
    'IsSalesOwner',
    'IsStoreObjectOwner',
    'IsStoreObjectOwnerOrReadOnly',
    'IsUserObjectOwner',
    'IsUserObjectOwnerOrReadOnly',
    'IsUserVerified',
]
