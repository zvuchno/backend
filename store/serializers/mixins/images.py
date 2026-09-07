"""Миксины для работы с изображениями в сериализаторах."""

from collections.abc import Iterable

from store.serializers.image import ImageSerializer


class ProductImagesMixin:
    """Миксин для подготовки изображений товаров."""

    @staticmethod
    def get_album_image_items(album) -> list[dict]:
        """Возвращает обложку альбома в формате списка изображений."""
        if not album or not album.cover_image:
            return []

        return [
            {
                'image': album.cover_image,
                'is_main': True,
            },
        ]

    @staticmethod
    def get_merch_image_items(images: Iterable) -> list[dict]:
        """Возвращает изображения мерча в формате списка изображений."""
        images = list(images)

        if not images:
            return []

        has_main = any(image.is_main for image in images)

        return [
            {
                'image': image.image,
                'is_main': image.is_main or (index == 0 and not has_main),
            }
            for index, image in enumerate(images)
        ]

    @staticmethod
    def get_main_image_item(items: list[dict]) -> dict | None:
        """Возвращает главное изображение из списка."""
        if not items:
            return None

        return next(
            (item for item in items if item.get('is_main')),
            items[0],
        )

    def serialize_image_items(self, items: list[dict]) -> list[dict]:
        """Сериализует список изображений."""
        return ImageSerializer(
            items,
            many=True,
            context=self.context,
        ).data

    def get_image_url(self, image_field) -> str | None:
        """Возвращает URL изображения."""
        if not image_field:
            return None

        try:
            url = image_field.url
        except ValueError:
            return None

        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url

    def get_main_image_url(self, items: list[dict]) -> str | None:
        """Возвращает URL главного изображения из списка."""
        main_image = self.get_main_image_item(items)

        if main_image is None:
            return None

        return self.get_image_url(main_image.get('image'))
