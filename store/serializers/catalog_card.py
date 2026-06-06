from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.serializers.mixins import ProductImagesMixin


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


class ProductCardSerializer(
    ProductImagesMixin,
    BaseCardSerializer,
):
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
        if obj.album_id:
            items = self.get_album_image_items(obj.album)
            return self.get_main_image_url(items)

        if obj.merch_id:
            items = self.get_merch_image_items(
                getattr(
                    obj.merch,
                    'prefetched_images',
                    obj.merch.images_merch.all(),
                ),
            )
            return self.get_main_image_url(items)

        if obj.track_id:
            items = self.get_album_image_items(obj.track.album)
            return self.get_main_image_url(items)

        return None


class CatalogCardTargetSerializer(serializers.Serializer):
    """Данные для перехода из карточки товара."""

    type = serializers.CharField(
        help_text=('Тип детальной карточки: release или merch.'),
    )
    url = serializers.CharField(
        allow_null=True,
        help_text='URL endpoint для перехода.',
    )
    selected_variant_id = serializers.IntegerField(
        help_text='Id варианта, который предвыбрать после перехода.',
        allow_null=True,
        default=None,
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

    DETAIL_URL_NAMES = {
        'release': 'api:store:catalog-release-detail',
        'merch': 'api:store:catalog-merch-detail',
    }

    class Meta(ProductCardSerializer.Meta):
        fields = ProductCardSerializer.Meta.fields + ('target',)

    @extend_schema_field(CatalogCardTargetSerializer)
    def get_target(self, obj):
        """Возвращает данные для перехода из карточки товара."""
        return {
            'type': obj.target_type,
            'url': self._get_target_url(obj.target_type, obj.target_id),
            'selected_variant_id': obj.selected_variant_id,
        }

    def _get_target_url(self, detail_type, detail_id) -> str | None:
        """Возвращает URL detail-ручки."""
        url_name = self.DETAIL_URL_NAMES.get(detail_type)

        if not url_name:
            return None

        return reverse(url_name, args=(detail_id,))
