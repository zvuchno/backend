"""Сериализаторы для работы с треками.

Содержит сериализаторы для чтения и записи данных модели Track,
используемые в API.
"""

from django.core.validators import FileExtensionValidator
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from common.access import can_manage_artist

from .mixins import ImmutableFieldsSerializerMixin
from store.constants import (
    ALLOWED_AUDIO_EXTENSIONS,
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
    SINGLE_TRACK_COUNT_ERROR,
)
from store.models import Album, ReleaseTrack
from store.services import TrackService
from store.services.album_archive import AlbumArchiveScheduler
from store.services.audio.schedule import TrackGeneratedAudioScheduler
from store.validators import validate_audiofile_size, validate_isrc_format


class TrackReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения Track."""

    price = serializers.DecimalField(
        source='product.price',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        read_only=True,
    )
    allow_overpay = serializers.BooleanField(
        source='product.allow_overpay',
        default=False,
    )
    artist_name = serializers.SerializerMethodField(
        read_only=True,
        allow_null=True,
    )
    is_favorite = serializers.BooleanField(read_only=True)

    name = serializers.CharField(
        source='recording.name',
        read_only=True,
    )
    album = serializers.PrimaryKeyRelatedField(
        source='release',
        read_only=True,
    )
    duration = serializers.IntegerField(
        source='recording.duration',
        allow_null=True,
        read_only=True,
    )
    image = serializers.ImageField(
        source='release.cover_image',
        read_only=True,
        allow_null=True,
    )

    @staticmethod
    def get_artist_name(obj) -> str | None:
        """Возвращает имя исполнителя альбома."""
        return obj.artist.name

    class Meta:
        model = ReleaseTrack
        fields = (
            'id',
            'artist_name',
            'name',
            'album',
            'duration',
            'position',
            'price',
            'allow_overpay',
            'image',
            'is_favorite',
        )


class TrackReadDetailSerializer(TrackReadSerializer):
    """Сериализатор для подробного просмотра (retrieve) объекта Track."""

    audio_file = serializers.FileField(
        source='recording.audio_file',
        read_only=True,
    )
    description = serializers.CharField(
        source='recording.description',
        read_only=True,
    )
    isrc = serializers.CharField(
        source='recording.isrc',
        allow_null=True,
        read_only=True,
    )

    class Meta(TrackReadSerializer.Meta):
        fields = TrackReadSerializer.Meta.fields + (
            'audio_file',
            'description',
            'isrc',
        )


class TrackWriteSerializer(
    ImmutableFieldsSerializerMixin,
    serializers.Serializer,
):
    """Сериализатор для создания и обновления."""

    immutable_fields = ('album',)
    immutable_field_sources = {
        'album': 'release',
    }

    name = serializers.CharField(
        max_length=MAX_CHAR_LENGTH,
    )
    album = serializers.PrimaryKeyRelatedField(
        queryset=Album.objects.all(),
    )
    audio_file = serializers.FileField(
        required=False,
        validators=(
            FileExtensionValidator(
                allowed_extensions=ALLOWED_AUDIO_EXTENSIONS,
            ),
            validate_audiofile_size,
        ),
    )
    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        required=False,
    )
    allow_overpay = serializers.BooleanField(required=False)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    isrc = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=12,
        validators=(validate_isrc_format,),
    )

    class Meta:
        model = ReleaseTrack

    def create(self, validated_data):
        album = validated_data.pop('album')
        created_by = validated_data.pop('created_by')

        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)

        track = TrackService.create(
            release=album,
            created_by=created_by,
            name=validated_data['name'],
            description=validated_data.get('description', ''),
            audio_file=validated_data.get('audio_file'),
            isrc=validated_data.get('isrc'),
        )

        TrackGeneratedAudioScheduler.schedule(track.recording)

        return track

    def update(self, instance, validated_data):
        validated_data.pop('album', None)
        validated_data.pop('price', None)
        validated_data.pop('allow_overpay', None)

        recording = instance.recording
        update_fields = []

        for field_name in ('name', 'description', 'audio_file', 'isrc'):
            if field_name not in validated_data:
                continue

            setattr(recording, field_name, validated_data[field_name])
            update_fields.append(field_name)

        if 'audio_file' in validated_data:
            recording.file_hash = ''
            update_fields.append('file_hash')

        if update_fields:
            recording.save(update_fields=update_fields)

        if 'audio_file' in validated_data:
            TrackGeneratedAudioScheduler.schedule(recording)

        if {'name', 'audio_file'} & validated_data.keys():
            release_ids = recording.release_tracks.values_list(
                'release_id',
                flat=True,
            ).distinct()

            for release_id in release_ids:
                transaction.on_commit(
                    lambda release_id=release_id: (
                        AlbumArchiveScheduler.schedule_by_id(release_id)
                    ),
                )

        return instance

    def validate(self, attrs):
        """Проверяет коммерческие параметры трека и ограничения сингла."""
        attrs = super().validate(attrs)

        if self.instance is not None:
            recording_fields = {
                'name',
                'description',
                'audio_file',
                'isrc',
            }

            if recording_fields.intersection(attrs) and not can_manage_artist(
                self.context['request'].user,
                self.instance.recording.owner,
            ):
                raise PermissionDenied(
                    'Нельзя изменять мастер-запись, '
                    'принадлежащую другому артисту.',
                )

        album = attrs.get(
            'album',
            self.instance.release if self.instance else None,
        )

        if album and album.release_type == Album.ReleaseType.SINGLE:
            errors = {}

            if 'price' in attrs:
                errors['price'] = (
                    'Для сингла нельзя задать индивидуальную цену трека.'
                )

            if 'allow_overpay' in attrs:
                errors['allow_overpay'] = (
                    'Для сингла нельзя настроить переплату за трек.'
                )
            # Нельзя добавить второй активный трек в опубликованный сингл
            if (
                self.instance is None
                and album.is_published
                and album.tracks.filter(is_active=True).exists()
            ):
                errors['album'] = SINGLE_TRACK_COUNT_ERROR

            if errors:
                raise serializers.ValidationError(errors)

        return attrs

    def validate_album(self, album):
        """Проверяет, что артист работает только со своим альбомом."""
        request = self.context['request']

        if not can_manage_artist(request.user, album.artist):
            raise serializers.ValidationError(
                'Нельзя добавить трек в чужой альбом.',
            )

        return album

    def validate_isrc(self, value):
        return value or None

    def to_representation(self, instance):
        """Возвращает сохранённый трек в формате detail API."""
        return TrackReadDetailSerializer(
            instance,
            context=self.context,
        ).data


class TrackReorderSerializer(serializers.Serializer):
    """Порядок треков альбома."""

    album = serializers.PrimaryKeyRelatedField(queryset=Album.objects.all())
    track_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_album(self, album):
        request = self.context['request']
        if not can_manage_artist(request.user, album.artist):
            raise serializers.ValidationError(
                'Нельзя менять порядок треков в чужом альбоме.',
            )
        return album

    def validate_track_ids(self, track_ids):
        if len(track_ids) != len(set(track_ids)):
            raise serializers.ValidationError(
                'Треки в списке не должны повторяться.',
            )
        return track_ids
