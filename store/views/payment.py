import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
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
        try:
            order = get_object_or_404(Order, id=order_id, user=request.user)
            # Вызываем сервис для создания платежа
            confirmation_url = create_yookassa_payment(order)
            return Response(
                {'confirmation_url': confirmation_url},
                status=status.HTTP_201_CREATED,
            )
        except Order.DoesNotExist:
            return Response(
                {'error': 'Заказ не найден'},
                status=status.HTTP_404_NOT_FOUND,
            )


@csrf_exempt
def yookassa_webhook(request):
    """Обрабатывает входящие уведомления (webhook) от ЮKassa.

    Функция считывает тело запроса, делегирует проверку подписи и
    бизнес-логику обработки событий сервисному слою. Всегда возвращает
    HTTP 200 OK для подтверждения получения уведомления, чтобы
    предотвратить повторные попытки отправки со стороны ЮKassa.
    """
    event_json = request.body.decode('utf-8')

    signature = request.META.get('HTTP_YOO_SIGNATURE')

    # Фабрика ЮKassa проверяет подпись и создает объект уведомления
    try:
        notification = WebhookNotificationFactory().create(
            event_json,
            signature,
        )
        process_yookassa_webhook(notification)
        return HttpResponse(status.HTTP_200_OK)
    except Exception as e:
        logger.error('Ошибка проверки подписи или обработки вебхука: %s', e)
        return HttpResponse(status.HTTP_400_BAD_REQUEST)
