"""Задачи обновления поискового индекса каталога."""

from celery import shared_task
from django.db import connection


@shared_task
def refresh_catalog_search():
    """Обновляет materialized view поискового индекса каталога."""
    with connection.cursor() as cursor:
        cursor.execute(
            'REFRESH MATERIALIZED VIEW CONCURRENTLY catalog_search;',
        )
