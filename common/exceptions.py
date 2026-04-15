"""Глобальный обработчик исключений для API проекта."""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exception, context):
    """Обрабатывает исключения DRF и логирует неожиданные ошибки API."""
    response = exception_handler(exception, context)
    view = context.get('view')
    request = context.get('request')

    if response is not None:
        logger.warning(
            'API error | %s | %s | status=%s | view=%s | detail=%s',
            request.method if request else 'UNKNOWN',
            request.path if request else 'UNKNOWN',
            response.status_code,
            view.__class__.__name__ if view else 'UNKNOWN',
            response.data,
        )
        return response

    logger.exception(
        'Unhandled API exception | %s | %s | view=%s',
        request.method if request else 'UNKNOWN',
        request.path if request else 'UNKNOWN',
        view.__class__.__name__ if view else 'UNKNOWN',
    )

    return Response(
        {'detail': 'Внутренняя  ошибка сервера.'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
