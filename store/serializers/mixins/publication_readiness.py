from rest_framework import serializers

from common.services import get_artist_publication_readiness


class PublicationReadinessValidationMixin:
    """Проверяет готовность артиста к публикации товара."""

    is_physical_product = False

    def validate_publication_readiness(self, attrs):
        """Проверяет возможность публикации товара."""
        if attrs.get('is_published') is not True:
            return attrs

        artist = attrs.get('artist')

        if artist is None and self.instance is not None:
            artist = self.instance.artist

        if artist is None:
            return attrs

        readiness = get_artist_publication_readiness(artist)

        if self.is_physical_product:
            can_publish = readiness.can_publish_physical
            missing = readiness.physical_missing
        else:
            can_publish = readiness.can_publish_digital
            missing = readiness.digital_missing

        if not can_publish:
            raise serializers.ValidationError({
                'is_published': [requirement.value for requirement in missing],
            })

        return attrs
