"""Инструкции для передачи файлов при загрузке треков."""

from dataclasses import dataclass
from datetime import datetime

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from django.conf import settings
from django.utils import timezone

from store.models import TrackUpload


class UploadTransportConfigurationError(RuntimeError):
    """Возникает при неполной настройке транспорта загрузки."""


@dataclass(frozen=True)
class UploadInstruction:
    """Инструкция для отправки файла клиентом."""

    method: str
    url: str
    headers: dict[str, str]
    fields: dict[str, str]
    file_field_name: str
    expires_at: datetime


class TrackUploadTransportService:
    """Выдаёт инструкцию для передачи файла в staging-хранилище."""

    @classmethod
    def create_instruction(
        cls,
        *,
        upload: TrackUpload,
        local_upload_url: str,
        local_upload_headers: dict[str, str] | None = None,
    ) -> UploadInstruction:
        """Возвращает инструкцию для загрузки файла конкретной попытки."""
        if settings.USE_S3_MEDIA:
            return cls._create_s3_instruction(upload=upload)

        return UploadInstruction(
            method='POST',
            url=local_upload_url,
            headers=local_upload_headers or {},
            fields={},
            file_field_name='file',
            expires_at=upload.expires_at,
        )

    @classmethod
    def _create_s3_instruction(
        cls,
        *,
        upload: TrackUpload,
    ) -> UploadInstruction:
        """Создаёт presigned POST-инструкцию для Object Storage."""
        cls._validate_s3_settings()

        fields: dict[str, str] = {}
        conditions: list[object] = [
            [
                'content-length-range',
                upload.expected_size,
                upload.expected_size,
            ],
        ]

        if upload.content_type:
            fields['Content-Type'] = upload.content_type
            conditions.append(
                {
                    'Content-Type': upload.content_type,
                },
            )

        response = cls._get_client().generate_presigned_post(
            Bucket=settings.AWS_PRIVATE_STORAGE_BUCKET_NAME,
            Key=cls._get_bucket_key(upload.staging_key),
            Fields=fields,
            Conditions=conditions,
            ExpiresIn=cls._get_expires_in(upload.expires_at),
        )

        return UploadInstruction(
            method='POST',
            url=response['url'],
            headers={},
            fields=response['fields'],
            file_field_name='file',
            expires_at=upload.expires_at,
        )

    @staticmethod
    def _validate_s3_settings() -> None:
        """Проверяет настройки Object Storage для прямой загрузки."""
        required_settings = (
            'AWS_PRIVATE_STORAGE_BUCKET_NAME',
            'AWS_ACCESS_KEY_ID',
            'AWS_SECRET_ACCESS_KEY',
            'AWS_S3_ENDPOINT_URL',
            'AWS_S3_REGION_NAME',
        )

        missing_settings = [
            setting_name
            for setting_name in required_settings
            if not getattr(settings, setting_name, '')
        ]

        if missing_settings:
            raise UploadTransportConfigurationError(
                'Не заполнены настройки Object Storage: '
                f'{", ".join(missing_settings)}.',
            )

    @staticmethod
    def _get_expires_in(expires_at: datetime) -> int:
        """Возвращает оставшееся время действия инструкции в секундах."""
        seconds = int((expires_at - timezone.now()).total_seconds())

        return max(seconds, 1)

    @staticmethod
    def _get_bucket_key(storage_key: str) -> str:
        """Добавляет location приватного storage к относительному ключу."""
        location = settings.MEDIA_LOCATION.strip('/')
        storage_key = storage_key.lstrip('/')

        if not location:
            return storage_key

        return f'{location}/{storage_key}'

    @staticmethod
    def _get_client() -> BaseClient:
        """Создаёт S3-клиент для Object Storage."""
        return boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            region_name=settings.AWS_S3_REGION_NAME,
            config=Config(
                s3={
                    'addressing_style': settings.AWS_S3_ADDRESSING_STYLE,
                },
            ),
        )
