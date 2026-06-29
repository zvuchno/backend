"""Сериализаторы данных для плеера."""

from rest_framework import serializers
from rest_framework.reverse import reverse

from .track import TrackReadSerializer
from store.models import Album, TrackGeneratedAudio


class TrackPlaybackSerializer(serializers.Serializer):
    """Данные доступного источника воспроизведения трека."""

    status = serializers.ChoiceField(
        choices=TrackGeneratedAudio.ProcessingStatus.choices,
        read_only=True,
    )
    kind = serializers.ChoiceField(
        choices=(
            ('preview', 'Превью'),
            ('full', 'Полная версия'),
        ),
        allow_null=True,
        read_only=True,
    )
    duration = serializers.IntegerField(
        allow_null=True,
        min_value=1,
        read_only=True,
    )
    url = serializers.CharField(
        allow_null=True,
        read_only=True,
    )

    def to_representation(self, instance):
        """Возвращает данные источника воспроизведения трека."""
        generated = getattr(instance, 'generated', None)

        if generated is None:
            return self._not_ready(
                TrackGeneratedAudio.ProcessingStatus.PENDING,
            )

        if generated.preview_status != (
            TrackGeneratedAudio.ProcessingStatus.READY
        ):
            return self._not_ready(generated.preview_status)

        if not generated.preview_file or not generated.preview_duration:
            return self._not_ready(
                TrackGeneratedAudio.ProcessingStatus.FAILED,
            )

        return {
            'status': TrackGeneratedAudio.ProcessingStatus.READY,
            'kind': 'preview',
            'duration': generated.preview_duration,
            'url': reverse(
                'api:store:player-play-track',
                kwargs={'track_id': instance.pk},
            ),
        }

    @staticmethod
    def _not_ready(status: str) -> dict:
        """Возвращает данные для неподготовленного источника."""
        return {
            'status': status,
            'kind': None,
            'duration': None,
            'url': None,
        }


class PlayerAlbumTrackSerializer(TrackReadSerializer):
    """Трек в очереди воспроизведения альбома."""

    playback = TrackPlaybackSerializer(
        source='*',
        read_only=True,
    )

    class Meta(TrackReadSerializer.Meta):
        fields = TrackReadSerializer.Meta.fields + ('playback',)


class PlayerAlbumSerializer(serializers.ModelSerializer):
    """Альбом и очередь треков для плеера."""

    tracks = PlayerAlbumTrackSerializer(
        many=True,
        read_only=True,
    )
    artist_name = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = (
            'id',
            'name',
            'artist_name',
            'cover_image',
            'tracks',
        )

    @staticmethod
    def get_artist_name(obj) -> str | None:
        """Возвращает имя исполнителя альбома."""
        artist = getattr(obj.owner, 'artist_profile', None)

        if artist is None:
            return None

        return artist.name


class PlaybackNotReadySerializer(serializers.Serializer):
    """Ошибка при недоступном для воспроизведения аудио."""

    detail = serializers.CharField(
        read_only=True,
    )
    status = serializers.ChoiceField(
        choices=TrackGeneratedAudio.ProcessingStatus.choices,
        read_only=True,
    )
