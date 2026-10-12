"""Глобальный обработчик исключений для API проекта."""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from store.exceptions import CDEKIntegrationError
from users.exceptions import SocialAuthException

logger = logging.getLogger(__name__)
expired_access_logger = logging.getLogger('common.exceptions.expired_access')


def _django_validation_error_to_data(exc) -> dict:
    """Преобразует Django ValidationError в формат API."""
    if hasattr(exc, 'message_dict'):
        return exc.message_dict

    if hasattr(exc, 'messages'):
        return {'detail': exc.messages}

    return {'detail': str(exc)}


def custom_exception_handler(exception, context):
    """Обрабатывает исключения DRF и логирует неожиданные ошибки API."""
    response = exception_handler(exception, context)
    view = context.get('view')
    request = context.get('request')

    if isinstance(exception, SocialAuthException):
        logger.warning(
            'Social auth error | %s | %s | view=%s | code=%s | detail=%s',
            request.method if request else 'UNKNOWN',
            request.path if request else 'UNKNOWN',
            view.__class__.__name__ if view else 'UNKNOWN',
            exception.error_code,
            exception.message,
        )
        return Response(
            {
                'error_code': exception.error_code,
                'detail': exception.message,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exception, CDEKIntegrationError):
        data = {
            'detail': str(exception),
        }

        if exception.code:
            data['code'] = exception.code

        if exception.error:
            data['error'] = exception.error

        return Response(
            data,
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if response is not None:
        data = response.data if isinstance(response.data, dict) else {}

        is_expired_access = (
            response.status_code == status.HTTP_401_UNAUTHORIZED
            and str(data.get('code')) == 'token_not_valid'
            and any(
                isinstance(item, dict)
                and str(item.get('token_type')) == 'access'
                and str(item.get('message')) == 'Token is expired'
                for item in (data.get('messages') or [])
            )
        )

        target_logger = expired_access_logger if is_expired_access else logger

        target_logger.log(
            logging.DEBUG if is_expired_access else logging.WARNING,
            'API error | %s | %s | status=%s | view=%s | detail=%s',
            request.method if request else 'UNKNOWN',
            request.path if request else 'UNKNOWN',
            response.status_code,
            view.__class__.__name__ if view else 'UNKNOWN',
            response.data,
        )
        return response

    if isinstance(exception, DjangoValidationError):
        data = _django_validation_error_to_data(exception)

        logger.warning(
            'Handled Django validation error | %s | %s | view=%s | data=%s',
            context['request'].method,
            context['request'].path,
            context.get('view').__class__.__name__,
            data,
        )
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

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
