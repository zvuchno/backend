from rest_framework import serializers

from store.constants import (
    MAX_CHAR_LENGTH,
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
    ZERO_MONEY,
)


class TrackUploadInitiateSerializer(serializers.Serializer):
    """Валидирует создание чернового трека и попытки загрузки."""

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
    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        required=False,
        default=ZERO_MONEY,
    )
    allow_overpay = serializers.BooleanField(
        required=False,
        default=False,
    )


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


class TrackUploadTrackSerializer(serializers.Serializer):
    """Описывает черновой или финализированный трек загрузки."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    position = serializers.IntegerField(allow_null=True)
    price = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
    )
    allow_overpay = serializers.BooleanField()


class TrackUploadStateSerializer(serializers.Serializer):
    """Описывает состояние попытки загрузки."""

    id = serializers.IntegerField()
    status = serializers.CharField()
    uploaded_size = serializers.IntegerField(allow_null=True)
    expires_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)
    complete_url = serializers.URLField()
    transport = TrackUploadTransportSerializer(required=False)


class TrackUploadResponseSerializer(serializers.Serializer):
    """Ответ API прямой загрузки трека."""

    track = TrackUploadTrackSerializer()
    upload = TrackUploadStateSerializer()


class TrackUploadLocalFileStateSerializer(serializers.Serializer):
    """Объект upload локальной ручки приёма файла."""

    id = serializers.IntegerField()
    status = serializers.CharField()
    uploaded_size = serializers.IntegerField()


class TrackUploadLocalFileResponseSerializer(serializers.Serializer):
    """Ответ локальной ручки приёма файла."""

    upload = TrackUploadLocalFileStateSerializer()
