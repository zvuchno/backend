import logging

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from store.schema import cdek_widget_schema
from store.services import CDEKService

logger = logging.getLogger(__name__)


@cdek_widget_schema
class CDEKWidgetView(APIView):
    """Эндпоинт-прокси для интеграции и обеспечения работы виджета СДЭК v3."""

    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle,)
    service = CDEKService()

    def get(self, request):
        action = request.query_params.get('action')

        logger.info(
            f'Получен запрос Widget-CDEK API. '
            f'Параметры: {dict(request.query_params)}',
        )

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
