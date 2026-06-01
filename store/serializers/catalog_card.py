from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION


class BaseCardSerializer(serializers.Serializer):
    """Базовый контракт витринной карточки товара.

    Не привязан к конкретной модели. Описывает форму карточки,
    которую можно собрать от Product, snapshot-а или другого источника.
    """

    name = serializers.CharField(
        read_only=True,
        help_text='Название товара.',
    )
    artist_name = serializers.CharField(
        read_only=True,
        allow_null=True,
        help_text='Имя артиста-владельца товара.',
    )
    kind = serializers.CharField(
        read_only=True,
        allow_null=True,
        help_text=(
            'Человекочитаемый вид карточки: Альбом, Сингл, '
            'Винил, Футболка, Трек и т.п.'
        ),
    )
    year = serializers.IntegerField(
        read_only=True,
        allow_null=True,
        help_text=(
            'Год релиза для музыкального контента. '
            'Для обычного мерча возвращается null.'
        ),
    )
    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
        help_text='Базовая цена товара.',
    )
    image = serializers.CharField(
        read_only=True,
        allow_null=True,
        help_text='Основное изображение карточки товара.',
    )
    is_favorite = serializers.BooleanField(
        read_only=True,
        help_text='Признак добавления товара в избранное.',
        default=False,
    )

    class Meta:
        fields = (
            'name',
            'artist_name',
            'kind',
            'year',
            'price',
            'image',
            'is_favorite',
        )


class ProductCardSerializer(BaseCardSerializer):
    """Сериализатор единой карточки товара.

    Базовая модель карточки — Product.

    Сериализатор используется для списков, где фронту нужна одинаковая
    товарная карточка: каталог, избранное, корзина, кабинет слушателя
    и похожие витринные выдачи.

    Если исходная ручка работает не с Product, а с другой сущностью,
    нужно передать в этот сериализатор связанный Product:

    - Album/Merch/Track -> instance.product;
    - Favorite -> favorite.product;
    - CartItem -> cart_item.product_variant.product;
    - OrderItem -> лучше использовать сохраненный snapshot карточки.

    Пример:
        CatalogCardSerializer(cart_item.product_variant.product).data
    """

    image = serializers.SerializerMethodField(
        help_text=(
            'Основное изображение карточки товара. '
            'Для трека временно используется обложка родительского альбома.'
        ),
    )
    is_favorite = serializers.SerializerMethodField(
        help_text='Признак добавления товара в избранное.',
        default=False,
    )

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_favorite(self, obj):
        """Возвращает признак добавления товара в избранное."""
        favorite_product_ids = self.context.get('favorite_product_ids', set())
        return obj.id in favorite_product_ids

    @extend_schema_field(OpenApiTypes.STR)
    def get_image(self, obj):
        """Возвращает изображение карточки товара."""
        request = self.context.get('request')

        if obj.album_id:
            image = obj.album.cover_image
            if not image:
                return None
            try:
                url = image.url
            except ValueError:
                return None

            return request.build_absolute_uri(url) if request else url

        if obj.merch_id:
            images = list(obj.merch.images_merch.all())
            if not images:
                return None

            main_image = next(
                (image for image in images if image.is_main),
                images[0],
            )

            try:
                url = main_image.image.url
            except ValueError:
                return None

            return request.build_absolute_uri(url) if request else url

        if obj.track_id:
            image = obj.track.album.cover_image
            if not image:
                return None

            try:
                url = image.url
            except ValueError:
                return None

            return request.build_absolute_uri(url) if request else url

        return None


class CatalogCardTargetSerializer(serializers.Serializer):
    """Данные для перехода из карточки товара."""

    type = serializers.CharField(
        help_text=(
            'Тип endpoint для перехода. Например: album, merch или track.'
        ),
    )
    url = serializers.CharField(
        allow_null=True,
        help_text='URL endpoint для перехода.',
    )


class VariantKeySerializer(serializers.Serializer):
    """Ключ варианта покупки.

    Для сопоставления карточки варианта на детальной странице.
    """

    type = serializers.CharField(
        help_text='Тип исходной сущности варианта: album, merch или track.',
    )
    id = serializers.IntegerField(
        help_text='ID исходной сущности варианта.',
    )


class CatalogCardSerializer(ProductCardSerializer):
    """Сериализатор карточки товара для публичного каталога."""

    target = serializers.SerializerMethodField(
        help_text=(
            'Данные для перехода по клику. '
            'Например, карточка носителя может вести '
            'на детальную карточку релиза.'
        ),
    )

    selected_variant_key = serializers.SerializerMethodField(
        help_text=(
            'Ключ варианта, который предвыбрать после перехода в detail.'
        ),
    )

    DETAIL_URL_NAMES = {
        'release': 'api:store:catalog-release-detail',
        'merch': 'api:store:catalog-merch-detail',
    }

    class Meta(ProductCardSerializer.Meta):
        fields = ProductCardSerializer.Meta.fields + (
            'target',
            'selected_variant_key',
        )

    @extend_schema_field(VariantKeySerializer)
    def get_selected_variant_key(self, obj):
        """Возвращает ключ для предвыбора варианта."""
        content = getattr(obj, 'content', None)
        if content is None:
            return None

        return {
            'type': obj.product_type,
            'id': obj.content_id,
        }

    @extend_schema_field(CatalogCardTargetSerializer)
    def get_target(self, obj):
        """Возвращает данные для перехода из карточки товара."""
        return {
            'type': obj.target_type,
            'url': self._get_target_url(obj.target_type, obj.target_id),
        }

    def _get_target_url(self, detail_type, detail_id) -> str | None:
        """Возвращает URL detail-ручки."""
        url_name = self.DETAIL_URL_NAMES.get(detail_type)

        if not url_name:
            return None

        return reverse(url_name, args=(detail_id,))
