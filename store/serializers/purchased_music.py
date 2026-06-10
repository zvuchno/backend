from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from store.models import ListenerAlbumAccess
from store.serializers.mixins import ProductImagesMixin


class LibraryAlbumCardSerializer(
    ProductImagesMixin,
    serializers.ModelSerializer,
):
    """Карточка доступного релиза в библиотеке слушателя."""

    id = serializers.IntegerField(
        source='album.id',
        help_text='id альбома',
        read_only=True,
    )
    name = serializers.CharField(
        source='album.name',
        help_text='Название товара.',
        read_only=True,
    )
    artist_name = serializers.SerializerMethodField(
        help_text='Имя артиста-владельца релиза.',
        read_only=True,
    )
    kind = serializers.SerializerMethodField(
        help_text=(
            'Человекочитаемый вид карточки: Альбом, Сингл, '
            'Винил, Футболка, Трек и т.п.'
        ),
        read_only=True,
    )
    year = serializers.SerializerMethodField(
        help_text=(
            'Год релиза для музыкального контента. '
            'Для обычного мерча возвращается null.'
        ),
        read_only=True,
    )
    image = serializers.SerializerMethodField(
        help_text='Основное изображение карточки релиза.',
        read_only=True,
    )
    is_fully_available = serializers.BooleanField(
        help_text='Признак полной доступности релиза.',
        read_only=True,
    )
    download_url = serializers.SerializerMethodField(
        help_text='URL для скачивания архива с доступными треками релиза.',
        read_only=True,
    )

    class Meta:
        model = ListenerAlbumAccess
        fields = (
            'id',
            'name',
            'artist_name',
            'kind',
            'year',
            'image',
            'is_fully_available',
            'download_url',
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_download_url(self, obj):
        """TODO. Возвращает URL скачивания доступных треков релиза."""
        return

    @extend_schema_field(OpenApiTypes.STR)
    def get_image(self, obj):
        """Возвращает изображение карточки релиза."""
        items = self.get_album_image_items(obj.album)
        return self.get_main_image_url(items)

    @extend_schema_field(OpenApiTypes.STR)
    def get_artist_name(self, obj) -> str | None:
        """Возвращает имя артиста-владельца."""
        artist = getattr(obj.album.owner, 'artist_profile', None)
        if artist is None:
            return None
        return artist.name

    @extend_schema_field(OpenApiTypes.STR)
    def get_kind(self, obj) -> str:
        """Возвращает тип релиза - альбом или сингл."""
        return 'Сингл' if obj.album.is_single else 'Альбом'

    @extend_schema_field(OpenApiTypes.INT)
    def get_year(self, obj) -> int:
        """Возвращает год релиза."""
        if not obj.album.release_date:
            return None
        return obj.album.release_date.year
