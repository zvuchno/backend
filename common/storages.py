"""Доступ к настроенным хранилищам медиафайлов."""

from django.core.files.storage import storages


def get_public_media_storage():
    """Возвращает хранилище публичных медиафайлов."""
    return storages['public_media']


def get_private_media_storage():
    """Возвращает хранилище приватных медиафайлов."""
    return storages['private_media']
