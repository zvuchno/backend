from users.models import (
    ArtistBankData,
    ArtistCompanyData,
    ArtistIdentityData,
    ArtistLegalProfile,
)


def create_artist_legal_profile(user, **kwargs) -> ArtistLegalProfile:
    """Создаёт заполненный юридический профиль пользователя."""
    legal_profile = ArtistLegalProfile.objects.create(
        user=user,
        email=kwargs.get('email', user.email),
        phone=kwargs.get('phone', '+79998887766'),
        recipient_type=kwargs.get(
            'recipient_type',
            ArtistLegalProfile.RecipientType.SELF_EMPLOYED,
        ),
        is_verified=kwargs.get('is_verified', False),
        comment=kwargs.get('comment', ''),
    )
    ArtistIdentityData.objects.create(
        legal_profile=legal_profile,
        first_name='Иван',
        last_name='Иванов',
        middle_name='Иванович',
        birth_date='1990-01-01',
        registration_address='г. Москва',
        passport_series='1234',
        passport_number='123456',
        passport_issued_by='500000',
        passport_issue_date='2010-01-01',
        inn='123456789012',
    )
    ArtistBankData.objects.create(
        legal_profile=legal_profile,
        bank_name='Тест-Банк',
        bik='123456789',
        correspondent_account='12345678901234567890',
        checking_account='12345678901234567890',
    )

    if kwargs.get('with_company_data', False):
        ArtistCompanyData.objects.create(
            legal_profile=legal_profile,
            company_name='ООО Тест',
            company_address='г. Москва',
            inn='1234567890',
            ogrn='1234567890123',
        )

    return legal_profile
