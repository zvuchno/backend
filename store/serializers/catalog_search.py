from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from common.storages import get_public_media_storage

from store.models import CatalogSearch
from store.serializers.catalog_card import CatalogCardTargetSerializer

_IMAGE_STORAGE = get_public_media_storage()


class CatalogSearchSerializer(serializers.ModelSerializer):
    """Сериализатор результата глобального поиска."""

    image = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()
    artist = serializers.CharField(
        source='artist_name',
        read_only=True,
        allow_null=True,
        help_text=(
            'Имя артиста для альбома, трека и мерча. '
            'Для остальных типов — null.'
        ),
    )

    class Meta:
        model = CatalogSearch
        fields = (
            'image',
            'artist',
            'kind',
            'name',
            'target',
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_image(self, obj):
        """Возвращает абсолютный URL изображения результата поиска."""
        if not obj.image:
            return None

        try:
            image_url = _IMAGE_STORAGE.url(obj.image)
        except (ValueError, OSError):
            return None

        request = self.context.get('request')

        if request:
            return request.build_absolute_uri(image_url)

        return image_url

    def _get_target_type(self, obj) -> str | None:
        """Возвращает тип детальной карточки."""
        if obj.entity_type in (
            CatalogSearch.EntityType.ALBUM,
            CatalogSearch.EntityType.TRACK,
        ):
            return 'release'

        if obj.entity_type == CatalogSearch.EntityType.MERCH:
            return 'merch'

        if obj.entity_type == CatalogSearch.EntityType.ARTIST:
            return 'artist'

        return None

    def _get_target_id(self, obj) -> int:
        """Возвращает id сущности для перехода — для трека это id альбома."""
        if obj.entity_type == CatalogSearch.EntityType.TRACK:
            return obj.target_id

        return obj.entity_id

    def _get_target_url(self, obj, target_type, target_id) -> str | None:
        """Возвращает URL detail-ручки.

        Публичная ручка артиста работает по slug — для
        entity_type=artist в reverse() передаём obj.target_slug.
        """
        if target_type == 'artist':
            if not obj.target_slug:
                return None

            return reverse('api:users:artist_public', args=(obj.target_slug,))

        if target_id is None:
            return None

        url_names = {
            'release': 'api:store:catalog-release-detail',
            'merch': 'api:store:catalog-merch-detail',
        }

        url_name = url_names.get(target_type)

        if not url_name:
            return None

        return reverse(url_name, args=(target_id,))

    @extend_schema_field(CatalogCardTargetSerializer)
    def get_target(self, obj):
        """Возвращает данные для перехода из результата поиска."""
        target_type = self._get_target_type(obj)
        target_id = self._get_target_id(obj)

        return {
            'type': target_type,
            'id': target_id,
            'url': self._get_target_url(obj, target_type, target_id),
            'selected_variant_id': obj.selected_variant_id,
        }
