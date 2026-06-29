import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from yookassa.domain.notification import WebhookNotificationFactory

from store.models import Order
from store.schema import payment_schema
from store.services import create_yookassa_payment, process_yookassa_webhook

logger = logging.getLogger(__name__)


@payment_schema
class CreatePaymentView(APIView):
    """Представление для инициализации платежа в ЮKassa.

    Принимает POST-запрос с идентификатором заказа, инициирует создание
    платежа через платежный шлюз и возвращает URL для перенаправления
    пользователя на страницу оплаты.
    """

    def post(self, request):
        order_id = request.data.get('order_id')
        order = get_object_or_404(
            Order,
            id=order_id,
            user=request.user,
        )

        result = create_yookassa_payment(order)

        return Response(
            {
                'status': result['payment_status'],
                'confirmation_url': result.get('confirmation_url'),
            },
            status=status.HTTP_200_OK,
        )


@csrf_exempt
@require_POST
def yookassa_webhook(request):
    """Обрабатывает входящие уведомления (webhook) от ЮKassa."""
    try:
        notification = WebhookNotificationFactory().create(request.body)
        process_yookassa_webhook(notification)
    except Exception:
        logger.exception('Ошибка обработки webhook ЮKassa.')
        return HttpResponse(status.HTTP_500_INTERNAL_SERVER_ERROR)

    return HttpResponse(status.HTTP_200_OK)
