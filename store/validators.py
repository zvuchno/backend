from django.core.exceptions import ValidationError

from .constants import MAX_IMAGE_SIZE_MB


def validate_file_size(value):
    """Ограничения размера обложки до 10 MB."""

    filesize = value.size

    if filesize > MAX_IMAGE_SIZE_MB * 1024 * 1024:  # MB в байтах
        raise ValidationError(
            f'Размер файла не должен превышать {MAX_IMAGE_SIZE_MB} MB')
    return value
