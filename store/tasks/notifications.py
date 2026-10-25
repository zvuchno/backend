"""Фоновые задачи Celery для асинхронной рассылки уведомлений артистам."""

from celery import shared_task

from store.models import Order, Shipment


@shared_task
def notify_artists_about_new_order_task(order_id: int) -> None:
    """Celery-задача для рассылки уведомлений артистам о заказе."""
    from store.notifications import notify_artists_about_new_order

    order = Order.objects.get(pk=order_id)
    notify_artists_about_new_order(order)


@shared_task
def notify_artist_about_cdek_order_task(shipment_id: int) -> None:
    """Celery-задача для уведомления артиста об отправлении СДЭК."""
    from store.notifications import notify_artist_about_cdek_order

    shipment = Shipment.objects.select_related(
        'artist__user',
        'artist__label__user',
        'artist__shipping_point',
        'artist__store_settings',
        'artist__label__shipping_point',
        'artist__label__store_settings',
        'order',
    ).get(pk=shipment_id)
    notify_artist_about_cdek_order(shipment)
