import logging

from celery import shared_task
from django.db import transaction

from store.exceptions import CDEKIntegrationError
from store.models import Order, Shipment
from store.services import CDEKService
from store.tasks.notifications import notify_artist_about_cdek_order_task

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
    retry_backoff_max=14400,
    retry_jitter=True,
    max_retries=10,
)
def update_cdek_shipment_task(self, shipment_id: int):
    """Ожидает завершения регистрации отправления в СДЭК."""
    try:
        shipment = Shipment.objects.select_related(
            'artist__user',
            'artist__label__user',
            'order',
        ).get(pk=shipment_id)
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

    if not state:
        logger.warning(
            'СДЭК не вернул состояние регистрации. uuid=%s',
            shipment.cdek_uuid,
        )
        raise self.retry()

    if state in (
        Shipment.State.ACCEPTED,
        Shipment.State.WAITING,
    ):
        logger.info(
            'Регистрация отправления %s ещё не завершена (%s).',
            shipment.cdek_uuid,
            state,
        )
        raise self.retry()

    if state == Shipment.State.INVALID:
        logger.error(
            'Регистрация отправления %s завершилась ошибкой: %s',
            shipment.cdek_uuid,
            request.get('errors'),
        )

        shipment.state = state
        shipment.save(update_fields=['state', 'updated_at'])
        return

    if state != Shipment.State.SUCCESSFUL:
        logger.warning(
            'Неизвестное состояние регистрации "%s" для uuid=%s.',
            state,
            shipment.cdek_uuid,
        )
        raise self.retry()

    cdek_number = entity.get('cdek_number')

    if not cdek_number:
        logger.warning(
            'СДЭК не вернул номер накладной для uuid=%s',
            shipment.cdek_uuid,
        )
        raise self.retry()

    with transaction.atomic():
        update_fields = ['state']

        if cdek_number and not shipment.cdek_number:
            shipment.cdek_number = cdek_number
            update_fields.append('cdek_number')
        elif cdek_number and shipment.cdek_number != cdek_number:
            logger.warning(
                'Номер заказа СДЭК не совпадает: shipment_id=%s, '
                'saved_cdek_number=%s, response_cdek_number=%s',
                shipment.pk,
                shipment.cdek_number,
                cdek_number,
            )

        shipment.state = state

        shipment.save(
            update_fields=[*update_fields, 'updated_at'],
        )

        transaction.on_commit(
            lambda: notify_artist_about_cdek_order_task.delay(shipment_id),
        )

    logger.info(
        'Отправление %s успешно зарегистрировано. Трек-номер: %s',
        shipment.cdek_uuid,
        shipment.cdek_number,
    )
