import logging

from celery import shared_task

from store.exceptions import CDEKIntegrationError
from store.models import Order, Shipment
from store.services import CDEKService

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(CDEKIntegrationError,),
    retry_backoff=60,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def register_cdek_orders_task(order_id):
    """Регистрирует накладные СДЭК для оплаченного заказа."""
    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning(
            'Регистрация отправлений СДЭК отменена: заказ с id=%s не найден.',
            order_id,
        )
        return

    if order.status != Order.Status.PAID:
        logger.warning(
            'Регистрация отправлений СДЭК пропущена: '
            'заказ %s имеет статус "%s", ожидается "%s".',
            order.order_number,
            order.status,
            Order.Status.PAID,
        )
        return

    logger.info(
        'Запущена регистрация отправлений СДЭК для заказа %s.',
        order.order_number,
    )
    CDEKService().register_orders(order)


@shared_task(
    bind=True,
    autoretry_for=(CDEKIntegrationError,),
    retry_backoff=30,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def update_cdek_shipment_task(self, shipment_id: int):
    """Ожидает завершения регистрации отправления в СДЭК."""
    try:
        shipment = Shipment.objects.get(pk=shipment_id)
    except Shipment.DoesNotExist:
        logger.warning(
            'Отправление id=%s не найдено.',
            shipment_id,
        )
        return

    data = CDEKService().get_order_info(shipment.cdek_uuid)

    requests = data.get('requests', [])
    entity = data.get('entity') or {}

    if not requests:
        logger.warning(
            'СДЭК не вернул информацию о запросе. uuid=%s',
            shipment.cdek_uuid,
        )
        raise self.retry()

    request = requests[0]
    state = request.get('state')

    if state in ('ACCEPTED', 'WAITING'):
        logger.info(
            'Регистрация отправления %s ещё не завершена (%s).',
            shipment.cdek_uuid,
            state,
        )
        raise self.retry()

    if state == 'INVALID':
        logger.error(
            'Регистрация отправления %s завершилась ошибкой: %s',
            shipment.cdek_uuid,
            request.get('errors'),
        )

        shipment.state = state
        shipment.save(update_fields=['state', 'updated_at'])
        return

    if state != 'SUCCESSFUL':
        logger.warning(
            'Неизвестное состояние регистрации "%s" для uuid=%s.',
            state,
            shipment.cdek_uuid,
        )
        raise self.retry()

    tracking_number = entity.get('cdek_number')

    if not tracking_number:
        logger.warning(
            'СДЭК не вернул номер накладной для uuid=%s',
            shipment.cdek_uuid,
        )
        raise self.retry()

    shipment.tracking_number = tracking_number
    shipment.state = state

    shipment.save(
        update_fields=[
            'tracking_number',
            'state',
            'updated_at',
        ],
    )

    logger.info(
        'Отправление %s успешно зарегистрировано. Трек-номер: %s',
        shipment.cdek_uuid,
        shipment.tracking_number,
    )
