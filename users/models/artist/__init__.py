"""Модели профиля артиста или лейбла."""

from .bank_data import ArtistBankData
from .company_data import ArtistCompanyData
from .contact import ArtistContact
from .identity_data import ArtistIdentityData
from .legal_profile import ArtistLegalProfile
from .pickup_point import ArtistPickupPoint
from .profile import ArtistProfile, ArtistProfileType
from .shipping_point import ArtistShippingPoint
from .social import ArtistSocial
from .store_settings import ArtistStoreSettings

__all__ = (
    'ArtistBankData',
    'ArtistCompanyData',
    'ArtistContact',
    'ArtistIdentityData',
    'ArtistLegalProfile',
    'ArtistPickupPoint',
    'ArtistProfile',
    'ArtistProfileType',
    'ArtistShippingPoint',
    'ArtistSocial',
    'ArtistStoreSettings',
)
