from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from store.models import AlbumArchive, ListenerAlbumAccess
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
        )

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


class PurchasedMusicDLItemSerializer(serializers.Serializer):
    """Вариант скачивания доступного релиза."""

    type = serializers.ChoiceField(
        choices=('archive', 'track'),
        read_only=True,
    )
    title = serializers.CharField(
        read_only=True,
    )
    status = serializers.ChoiceField(
        choices=AlbumArchive.Status.choices,
        read_only=True,
    )
    download_action_url = serializers.URLField(
        allow_null=True,
        read_only=True,
        help_text=(
            'URL POST-ручки для получения свежей временной ссылки '
            'на скачивание. null, если скачивание пока недоступно.'
        ),
    )


class PurchasedMusicDLDetailSerializer(serializers.Serializer):
    """Детальная информация для скачивания релиза."""

    album_id = serializers.IntegerField(
        source='album.id',
        read_only=True,
    )
    access = serializers.SerializerMethodField()
    items = serializers.SerializerMethodField()

    def get_access(self, album_access) -> str:
        """Возвращает тип доступа пользователя к релизу."""
        return 'full' if album_access.is_fully_available else 'partial'

    @extend_schema_field(PurchasedMusicDLItemSerializer(many=True))
    def get_items(self, album_access) -> list[dict]:
        """Возвращает доступные варианты скачивания."""
        items = []

        archive = self.context.get('archive')

        if archive is not None:
            items.append(self._get_archive_item(archive))

        for track in self.context['tracks']:
            items.append(self._get_track_item(track))

        return items

    def _get_archive_item(self, archive) -> dict:
        """Возвращает представление ZIP-архива."""
        return {
            'type': 'archive',
            'title': 'Скачать альбом в .ZIP',
            'status': archive.status,
            'download_action_url': self._build_download_action_url(
                view_name='api:store:purchased-music-archive-download-link',
                args=(archive.album_id,),
                is_available=archive.status == AlbumArchive.Status.READY,
            ),
        }

    def _get_track_item(self, track) -> dict:
        """Возвращает представление отдельного трека."""
        title = track.name

        if track.position is not None:
            title = f'{track.position:02d}. {track.name}'

        return {
            'type': 'track',
            'title': title,
            'status': AlbumArchive.Status.READY,
            'download_action_url': self._build_download_action_url(
                view_name='api:store:purchased-music-track-download-link',
                args=(track.pk,),
            ),
        }

    def _build_download_action_url(
        self,
        *,
        view_name: str,
        args: tuple[int, ...],
        is_available: bool = True,
    ) -> str | None:
        """Возвращает относительный URL POST-ручки или null."""
        if not is_available:
            return None

        return reverse(view_name, args=args)


class DownloadLinkSerializer(serializers.Serializer):
    """Временная ссылка на скачивание приватного файла."""

    url = serializers.SerializerMethodField()
    filename = serializers.CharField(read_only=True)
    expires_in = serializers.IntegerField(
        allow_null=True,
        read_only=True,
    )
    expires_at = serializers.DateTimeField(
        allow_null=True,
        read_only=True,
    )

    def get_url(self, link) -> str:
        """Возвращает абсолютный URL ссылки."""
        request = self.context.get('request')

        if request is None:
            return link.url

        return request.build_absolute_uri(link.url)


class ArchiveNotReadySerializer(serializers.Serializer):
    """Состояние неподготовленного альбомного архива."""

    detail = serializers.CharField()
    status = serializers.ChoiceField(
        choices=AlbumArchive.Status.choices,
    )
