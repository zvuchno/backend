from django.conf import settings
from django.urls import reverse
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .catalog_card import CatalogCardTargetSerializer


class BaseVariantTargetImageSerializer(serializers.ModelSerializer):
    """Базовый сериализатор элемента списка, связанного с ProductVariant.

    Применяется для list-эндпоинтов (корзина, избранное, заказы),
    где объект представлен как элемент списка товаров с логикой перехода.
    Добавляет общие поля представления:
    - target: данные для перехода на целевую сущность (album / merch);
    - image: изображение для отображения в списке.
    """

    DETAIL_URL_NAMES = {
        'release': 'api:store:catalog-release-detail',
        'merch': 'api:store:catalog-merch-detail',
    }

    image = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField(
        help_text=(
            'Данные для перехода по клику. '
            'Например, карточка носителя может вести на detail альбома.'
        ),
        read_only=True,
    )

    class Meta:
        fields = (
            'image',
            'target',
        )

    @extend_schema_field(CatalogCardTargetSerializer)
    def get_target(self, obj):
        """Возвращает данные для перехода на карточку товара."""
        return {
            'type': obj.target_type,
            'url': self._get_target_url(obj),
            'selected_variant_id': obj.product_variant_id,
        }

    def _get_target_url(self, obj) -> str | None:
        """Возвращает URL detail-эндпойнта."""
        url_name = self.DETAIL_URL_NAMES.get(obj.target_type)

        if not url_name:
            return None

        return reverse(url_name, args=(obj.target_id,))

    def get_image(self, obj):
        image_path = getattr(obj, 'image_path', None)

        if not image_path:
            return None

        request = self.context.get('request')

        if request:
            return request.build_absolute_uri(
                settings.MEDIA_URL + image_path,
            )

        return settings.MEDIA_URL + image_path
