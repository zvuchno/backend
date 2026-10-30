import json
import logging
import secrets

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from common.utils.get_client_ip import get_client_ip

from store.models import Shipment
from store.schema import (
    cdek_calculate_schema,
    cdek_cities_suggest_schema,
    cdek_widget_schema,
)
from store.serializers import CdekCalculateSerializer
from store.services import CDEKService, CartService
from store.services.shipment import (
    RESULT_APPLIED,
    apply_status_event,
    parse_event_time,
)

logger = logging.getLogger(__name__)


@cdek_widget_schema
class CDEKWidgetView(APIView):
    """Эндпоинт-прокси для интеграции и обеспечения работы виджета СДЭК v3."""

    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle,)
    service = CDEKService()

    def get(self, request):
        logger.info(
            'Получен GET запрос Widget-CDEK API. Параметры: %s',
            dict(request.query_params),
        )
        action = request.query_params.get('action')

        if action == 'offices':
            # Передаем QueryDict в сервис
            result = self.service.get_offices(request.query_params)

            # Формируем ответ с кастомными заголовками для виджета
            response = Response(result['points'], status=status.HTTP_200_OK)
            response['X-Current-Page'] = str(result['page'])
            response['X-Total-Elements'] = str(result['total_elements'])
            response['X-Total-Pages'] = str(result['total_pages'])
            response['Access-Control-Expose-Headers'] = (
                'X-Current-Page, X-Total-Elements, X-Total-Pages'
            )
            return response

        logger.error('unknown get action: %s', action)
        return Response(
            {'error': f'unknown get action: {action}'},
            status=status.HTTP_400_BAD_REQUEST,
        )


@cdek_calculate_schema
class CdekCalculateView(APIView):
    """Принимает код города и запрашивает стоимость доставки в API СДЭК."""

    permission_classes = (IsAuthenticated,)
    throttle_classes = (UserRateThrottle,)

    def post(self, request, *args, **kwargs):
        cart = CartService.get_or_create_cart(request)

        serializer = CdekCalculateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        city_code = serializer.validated_data['city_code']
        tariffs = serializer.validated_data['tariffs']

        cdek_service = CDEKService()
        result = cdek_service.calculate(
            city_code=str(city_code),
            cart=cart,
            tariffs=tariffs,
        )

        return Response(result, status=status.HTTP_200_OK)


@cdek_cities_suggest_schema
class CdekCitiesView(APIView):
    """Отдает подсказки по подбору населенного пункта по его наименованию."""

    permission_classes = (IsAuthenticated,)
    throttle_classes = (UserRateThrottle,)

    def get(self, request, *args, **kwargs):
        query = request.query_params.get('query', '').strip()

        if not query or len(query) < 2:  # Минимум 2 символа для поиска
            return Response([], status=status.HTTP_200_OK)

        cdek_service = CDEKService()
        result = cdek_service.suggest_cities(query=query)

        return Response(result, status=status.HTTP_200_OK)


@csrf_exempt
@require_http_methods(['POST'])
def cdek_webhook_view(request, token):
    """Эндпоинт для приёма вебхуков от СДЭК."""
    if not _token_is_valid(token):
        logger.warning(
            'СДЭК: запрос с неверным токеном, ip=%s',
            get_client_ip(request),
        )
        return HttpResponse(status=status.HTTP_403_FORBIDDEN)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning('СДЭК: получен некорректный JSON')
        return _bad_request('Invalid JSON')

    if not isinstance(data, dict):
        logger.warning('СДЭК: получена некорректная структура запроса')
        return _bad_request('Invalid payload')

    if data.get('type') != 'ORDER_STATUS':
        return _ok()

    cdek_uuid = data.get('uuid')
    attributes = data.get('attributes')

    if not isinstance(attributes, dict):
        logger.warning(
            'СДЭК: отсутствуют атрибуты события, uuid=%s',
            cdek_uuid,
        )
        return _bad_request('Invalid attributes')

    status_code = attributes.get('code')
    if not cdek_uuid or not status_code:
        logger.warning(
            'СДЭК: отсутствует uuid или код статуса, uuid=%s',
            cdek_uuid,
        )
        return _bad_request('Missing uuid or status code')

    if status_code not in Shipment.DeliveryStatus.values:
        logger.warning(
            'СДЭК: неизвестный статус: uuid=%s, status=%s',
            cdek_uuid,
            status_code,
        )
        return _ok()

    cdek_number = attributes.get('cdek_number')
    cdek_number = str(cdek_number) if cdek_number else ''

    occurred_at = parse_event_time(
        attributes.get('status_date_time') or data.get('date_time'),
    )

    result = apply_status_event(
        cdek_uuid=cdek_uuid,
        status_code=status_code,
        occurred_at=occurred_at,
        cdek_number=cdek_number,
        raw=data,
    )

    if result == RESULT_APPLIED:
        logger.info(
            'СДЭК: обновлён статус отправления: uuid=%s, status=%s',
            cdek_uuid,
            status_code,
        )

    return _ok()


def _token_is_valid(token: str) -> bool:
    expected = settings.CDEK_WEBHOOK_TOKEN
    if not expected:
        return False
    return secrets.compare_digest(token.encode(), expected.encode())


def _ok() -> JsonResponse:
    return JsonResponse({'status': 'success'}, status=status.HTTP_200_OK)


def _bad_request(message: str) -> JsonResponse:
    return JsonResponse(
        {'error': message},
        status=status.HTTP_400_BAD_REQUEST,
    )
