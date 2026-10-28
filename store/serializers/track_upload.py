from rest_framework import serializers

from store.constants import (
    MAX_CHAR_LENGTH,
)
from store.models import Recording, ReleaseTrack, TrackUpload
from store.validators import validate_isrc_format
from users.models import ArtistProfile


class TrackUploadInitiateSerializer(serializers.Serializer):
    """Валидирует создание мастер-записи и начало загрузки оригинала."""

    artist = serializers.PrimaryKeyRelatedField(
        queryset=ArtistProfile.objects.all(),
        source='owner',
    )
    filename = serializers.CharField(max_length=MAX_CHAR_LENGTH)
    size = serializers.IntegerField(min_value=1)
    content_type = serializers.CharField(
        max_length=MAX_CHAR_LENGTH,
        required=False,
        allow_blank=True,
        default='',
    )

    name = serializers.CharField(
        max_length=MAX_CHAR_LENGTH,
        required=False,
        allow_blank=True,
        default='',
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
    )
    isrc = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=12,
        validators=(validate_isrc_format,),
    )

    def validate_isrc(self, value):
        """Приводит пустой ISRC к отсутствующему значению."""
        return value or None


class TrackUploadTransportSerializer(serializers.Serializer):
    """Описывает инструкцию для отправки файла клиентом."""

    method = serializers.CharField()
    url = serializers.URLField()
    headers = serializers.DictField(
        child=serializers.CharField(),
    )
    fields = serializers.DictField(
        child=serializers.CharField(),
    )
    file_field_name = serializers.CharField()


class TrackUploadRecordingSerializer(serializers.Serializer):
    """Данные мастер-записи в ответе direct upload."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    isrc = serializers.CharField(allow_null=True)


class TrackUploadStateSerializer(serializers.Serializer):
    """Описывает состояние попытки загрузки."""

    id = serializers.IntegerField()
    status = serializers.ChoiceField(
        choices=TrackUpload.Status.choices,
    )
    uploaded_size = serializers.IntegerField(allow_null=True)
    expires_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)
    complete_url = serializers.URLField()
    transport = TrackUploadTransportSerializer(required=False)


class TrackUploadResponseSerializer(serializers.Serializer):
    """Ответ API прямой загрузки мастер-записи."""

    recording = TrackUploadRecordingSerializer()
    upload = TrackUploadStateSerializer()


class TrackUploadLocalFileStateSerializer(serializers.Serializer):
    """Объект upload локальной ручки приёма файла."""

    id = serializers.IntegerField()
    status = serializers.ChoiceField(
        choices=TrackUpload.Status.choices,
    )
    uploaded_size = serializers.IntegerField()


class TrackUploadLocalFileResponseSerializer(serializers.Serializer):
    """Ответ локальной ручки приёма файла."""

    upload = TrackUploadLocalFileStateSerializer()


class TrackReplacementUploadInitiateSerializer(serializers.Serializer):
    """Валидирует замену оригинала по track_id или recording_id."""

    filename = serializers.CharField(max_length=MAX_CHAR_LENGTH)
    size = serializers.IntegerField(min_value=1)
    content_type = serializers.CharField(
        max_length=MAX_CHAR_LENGTH,
        required=False,
        allow_blank=True,
        default='',
    )

    track_id = serializers.PrimaryKeyRelatedField(
        source='release_track',
        queryset=ReleaseTrack.objects.select_related('recording'),
        required=False,
    )
    recording_id = serializers.PrimaryKeyRelatedField(
        source='recording',
        queryset=Recording.objects.all(),
        required=False,
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        release_track = attrs.pop('release_track', None)
        recording = attrs.get('recording')

        if release_track is None and recording is None:
            raise serializers.ValidationError(
                'Необходимо указать track_id или recording_id.',
            )

        if release_track is not None:
            if (
                recording is not None
                and recording.pk != release_track.recording_id
            ):
                raise serializers.ValidationError({
                    'recording_id': (
                        'Указанные track_id и recording_id '
                        'относятся к разным записям.'
                    ),
                })

            attrs['recording'] = release_track.recording

        return attrs
