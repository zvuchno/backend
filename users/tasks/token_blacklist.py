"""Celery-задачи обслуживания JWT-токенов."""

from celery import shared_task
from django.core.management import call_command


@shared_task
def flush_expired_tokens() -> None:
    """Удаляет истёкшие JWT-токены из outstanding- и blacklist-таблиц."""
    call_command('flushexpiredtokens')
