from django.urls import reverse
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from store.constants import MAX_PRICE_DIGITS, MONEY_DISPLAY_PRECISION
from store.models import Product


class CatalogCardDetailSerializer(serializers.Serializer):
    """Сериализатор блока перехода на detail-страницу.

    type - тип для выбора detail ручки.
    id - идентификатор объекта detail-ручки.
    target_url - URL detail-ручки.
    preselect_variant_id - для предвыбора варианта товара,
    например при переходе из card винила на detail карточку альбома.
    """

    type = serializers.CharField(
        help_text='Тип detail-ручки, которую должен открыть фронт.',
    )
    id = serializers.IntegerField(
        help_text='Идентификатор объекта detail-ручки.',
    )
    target_url = serializers.CharField(
        allow_null=True,
        help_text='URL detail-ручки.',
    )
    preselect_variant_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text=(
            'ID варианта товара, который нужно предвыбрать на detail-странице.'
        ),
    )


class CatalogCardSerializer(serializers.ModelSerializer):
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

    Для корзины и других ручек с уже выбранным вариантом можно передать
    вариант через context['preselect_variant']. Тогда его id попадет
    в detail.preselect_variant_id.

    Пример:
        CatalogCardSerializer(
            cart_item.product_variant.product,
            context={
                **self.context,
                'preselect_variant': cart_item.product_variant,
            },
        ).data
    """

    artist_name = serializers.SerializerMethodField(
        help_text='Имя артиста-владельца товара.',
    )
    kind = serializers.SerializerMethodField(
        help_text=(
            'Человекочитаемый вид карточки: Альбом, Сингл, '
            'Винил, Футболка и т.п.'
        ),
    )
    year = serializers.SerializerMethodField(
        help_text='Год релиза для музыкального контента.',
    )
    image = serializers.SerializerMethodField(
        help_text='Основное изображение карточки товара.',
    )
    is_favorite = serializers.SerializerMethodField(
        help_text='Признак добавления товара в избранное. ',
    )
    detail = serializers.SerializerMethodField(
        help_text='Данные для перехода из карточки товара на detail-ручку.',
    )
    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
        help_text='Базовая цена товара.',
    )

    DETAIL_URL_NAMES = {
        'album': 'api:store:albums-detail',
        'merch': 'api:store:merch-detail',
        'track': 'api:store:tracks-detail',
    }

    class Meta:
        model = Product
        fields = (
            'id',
            'product_type',
            'name',
            'artist_name',
            'kind',
            'year',
            'price',
            'image',
            'is_favorite',
            'detail',
        )

    def get_is_favorite(self, obj):
        """TODO."""
        return False

    def get_artist_name(self, obj):
        owner = getattr(obj.content, 'owner', None)
        artist_profile = getattr(owner, 'artist_profile', None)
        return artist_profile.name if artist_profile else None

    def get_kind(self, obj):
        if obj.album_id:
            return 'Сингл' if obj.album.is_single else 'Альбом'

        if obj.merch_id:
            merch = obj.merch
            return merch.kind.name if merch.kind else None

        if obj.track_id:
            return 'Трек'

        return None

    def get_year(self, obj):
        if obj.album_id and obj.album.release_date:
            return obj.album.release_date.year
        return None

    @extend_schema_field(CatalogCardDetailSerializer)
    def get_detail(self, obj):
        """Возвращает данные для перехода на detail-страницу."""
        detail_type = obj.product_type
        detail_id = obj.content.id

        is_carrier = (
            obj.merch_id and obj.merch.album_id and obj.merch.is_carrier
        )

        # Носитель уйдет на detail альбома.
        if is_carrier:
            detail_type = 'album'
            detail_id = obj.merch.album_id

        detail = {
            'type': detail_type,
            'id': detail_id,
            'target_url': self.get_target_url(detail_type, detail_id),
        }

        # Если передан выбранный вариант, например из корзины или заказа.
        preselect_variant = self.context.get('preselect_variant')

        if (
            preselect_variant is not None
            and preselect_variant.product_id == obj.id
        ):
            detail['preselect_variant_id'] = preselect_variant.id
            return detail

        # Свой вариант у каждого носителя как выбранный на detail альбома.
        if obj.album_id or is_carrier:
            active_variants = getattr(obj, 'active_variants', None)
            # если сделан prefetch to_attr='active_variants'
            if active_variants is not None:
                default_variant = (
                    active_variants[0] if active_variants else None
                )
            else:
                default_variant = (
                    obj.variants.filter(is_active=True).order_by('id').first()
                )

            if default_variant is not None:
                detail['preselect_variant_id'] = default_variant.id

        return detail

    def get_target_url(self, detail_type, detail_id):
        """Возвращает URL detail-ручки."""
        url_name = self.DETAIL_URL_NAMES.get(detail_type)

        if not url_name:
            return None

        return reverse(url_name, args=(detail_id,))

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

        return None
