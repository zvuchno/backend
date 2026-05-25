from drf_spectacular.utils import extend_schema

from store.serializers import ImageSerializer


def image_detail_schema(view_func):
    """Декоратор для документирования изображения мерча (PATCH и DELETE)."""
    return extend_schema(
        methods=['patch'],
        summary='Обновить изображение',
        tags=['Merch'],
        description='Обновляет изображение мерча.',
        request=ImageSerializer,
        responses={200: ImageSerializer},
    )(
        extend_schema(
            methods=['delete'],
            summary='Удалить изображение',
            tags=['Merch'],
            description='Удаляет изображение мерча.',
            responses={204: None},
        )(view_func),
    )


def add_image_schema(view_func):
    """Декоратор для документирования экшена добавления изображения к мерчу."""
    return extend_schema(
        summary='Добавить изображение',
        tags=['Merch'],
        description='Добавляет изображение к мерчу.',
        request=ImageSerializer,
        responses={201: ImageSerializer},
    )(view_func)
