import pytest
from django.core.exceptions import ValidationError

from store.validators import validate_isrc_format


@pytest.mark.parametrize(
    'isrc',
    (
        'RUA1B2600001',
        'USRC17607839',
        'GBAYE6800011',
    ),
)
def test_validate_isrc_format_accepts_valid_isrc(isrc):
    """Валидатор принимает корректные ISRC."""
    validate_isrc_format(isrc)


@pytest.mark.parametrize(
    'isrc',
    (
        'RUA1B260001',  # слишком короткий
        'RUA1B26000001',  # слишком длинный
        'ruA1B2600001',  # lowercase
        'RU-A1B-26-00001',  # дефисы
        '1UA1B2600001',  # country code не из букв
        'RUA_B2600001',  # недопустимый символ registrant
        'RUA1B2A00001',  # буква в цифровой части
    ),
)
def test_validate_isrc_format_rejects_invalid_isrc(isrc):
    """Валидатор отклоняет ISRC с некорректным форматом."""
    with pytest.raises(ValidationError) as exc_info:
        validate_isrc_format(isrc)

    assert exc_info.value.code == 'invalid_isrc_format'
