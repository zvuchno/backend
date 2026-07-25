"""Публичные пермишены проекта.

Экспортирует готовые к использованию классы пермишенов для:
- ролевого доступа;
- доступа по владельцу объекта;
- проверки подтверждённого аккаунта.
"""

from .ownership import (
    IsSalesOwner,
    IsStoreObjectManager,
    IsStoreObjectManagerOrReadOnly,
    IsStoreObjectOwner,
    IsUserObjectOwner,
    IsUserObjectOwnerOrReadOnly,
)
from .profiles import (
    CanCreateArtistContent,
    IsArtist,
    IsArtistOrLabel,
    IsLabel,
    IsListener,
    IsNotArtist,
)
from .verification import IsUserVerified

__all__ = [
    'CanCreateArtistContent',
    'IsArtist',
    'IsArtistOrLabel',
    'IsLabel',
    'IsListener',
    'IsNotArtist',
    'IsSalesOwner',
    'IsStoreObjectManager',
    'IsStoreObjectManagerOrReadOnly',
    'IsStoreObjectOwner',
    'IsUserObjectOwner',
    'IsUserObjectOwnerOrReadOnly',
    'IsUserVerified',
]
