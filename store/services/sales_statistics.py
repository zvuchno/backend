from dataclasses import dataclass

from django.db.models import Exists, OuterRef, Q, QuerySet, Sum

from store.models import Album, Order, OrderItem, Payment, Track


@dataclass(frozen=True)
class ReleaseSalesStats:
    """Статистика прямых продаж релиза."""

    direct_sales: int


@dataclass(frozen=True)
class TrackSalesStats:
    """Статистика приобретений трека."""

    direct_sales: int
    release_sales: int

    @property
    def total_sales(self) -> int:
        """Возвращает общее число приобретений трека."""
        return self.direct_sales + self.release_sales


def _paid_order_items() -> QuerySet:
    """Возвращает позиции заказов с подтверждённой оплатой."""
    succeeded_payment = Payment.objects.filter(
        order_id=OuterRef('order_id'),
        status=Payment.PaymentStatus.SUCCEEDED,
    )

    return OrderItem.objects.annotate(
        has_succeeded_payment=Exists(succeeded_payment),
    ).filter(
        Q(
            order__status__in=(
                Order.Status.PAID,
                Order.Status.SHIPPED,
                Order.Status.COMPLETED,
            ),
        )
        | Q(has_succeeded_payment=True),
    )


def _sum_quantity(queryset) -> int:
    """Возвращает суммарное количество проданных единиц."""
    return (
        queryset.aggregate(
            total=Sum('quantity'),
        )['total']
        or 0
    )


def get_release_sales_stats(album: Album) -> ReleaseSalesStats:
    """Возвращает статистику прямых продаж релиза."""
    items = _paid_order_items().filter(
        product_variant__product__album_id=album.pk,
    )

    return ReleaseSalesStats(
        direct_sales=_sum_quantity(items),
    )


def get_track_sales_stats(track: Track) -> TrackSalesStats:
    """Возвращает статистику приобретений трека."""
    paid_items = _paid_order_items()

    direct_sales = _sum_quantity(
        paid_items.filter(
            product_variant__product__track_id=track.pk,
        ),
    )
    release_sales = _sum_quantity(
        paid_items.filter(
            product_variant__product__album_id=track.album_id,
        ),
    )

    return TrackSalesStats(
        direct_sales=direct_sales,
        release_sales=release_sales,
    )


def tracks_have_sales(queryset: QuerySet[Track]) -> bool:
    """Проверяет наличие продаж у переданных треков."""
    track_ids = queryset.values('pk')
    release_ids = queryset.values('album_id')

    return (
        _paid_order_items()
        .filter(
            Q(
                product_variant__product__track_id__in=track_ids,
            )
            | Q(
                product_variant__product__album_id__in=release_ids,
            ),
        )
        .exists()
    )
