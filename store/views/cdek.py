import logging

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from store.schema import (
    cdek_calculate_schema,
    cdek_cities_suggest_schema,
    cdek_widget_schema,
)
from store.serializers import CdekCalculateSerializer
from store.services import CDEKService, CartService

logger = logging.getLogger(__name__)


@cdek_widget_schema
class CDEKWidgetView(APIView):
    """Эндпоинт-прокси для интеграции и обеспечения работы виджета СДЭК v3."""

    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle,)
    service = CDEKService()

    def get(self, request):
        logger.info(
            f'Получен GET запрос Widget-CDEK API. '
            f'Параметры: {dict(request.query_params)}',
        )
        action = request.query_params.get('action')

        if action == 'offices':
            # Передаем QueryDict в сервис
            result = self.service.get_offices(request.query_params)

            # Формируем ответ с кастомными заголовками для виджета
            response = Response(result['points'], status=200)
            response['X-Current-Page'] = str(result['page'])
            response['X-Total-Elements'] = str(result['total_elements'])
            response['X-Total-Pages'] = str(result['total_pages'])
            response['Access-Control-Expose-Headers'] = (
                'X-Current-Page, X-Total-Elements, X-Total-Pages'
            )
            return response

        logging.error(f'unknown get action: {action}')
        return Response({'error': f'unknown get action: {action}'}, status=400)


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
        cdek_delivery_mode = serializer.validated_data['cdek_delivery_mode']

        cdek_service = CDEKService()
        result = cdek_service.calculate(
            city=str(city_code),
            cart=cart,
            cdek_delivery_mode=cdek_delivery_mode,
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
