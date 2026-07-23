"""Сервис формирования финансовых отчетов артистов."""

import datetime
import logging
from datetime import date

from django.db import transaction
from django.db.models import (
    Count,
    DecimalField,
    F,
    Q,
    Sum,
    Value,
)
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Coalesce, Greatest
from django.utils import timezone

from store.constants import (
    MAX_PRICE_DIGITS,
    MONEY_INTERNAL_PRECISION,
    ZERO_MONEY,
)
from store.models import Order, OrderItem, Report
from users.models import ArtistProfile

logger = logging.getLogger(__name__)


class ReportService:
    """Сервис формирования агрегированных отчетов."""

    PAID_STATUSES = (
        Order.Status.PAID,
        Order.Status.SHIPPED,
        Order.Status.COMPLETED,
    )

    @classmethod
    def generate(
        cls,
        *,
        artist: ArtistProfile,
        period_type: str,
        period_start: date,
        period_end: date,
    ) -> Report:
        """Формирует отчет артиста за указанный период."""
        if period_start > period_end:
            raise ValueError('period_start должен быть <= period_end')
        try:
            with transaction.atomic():
                tz = timezone.get_current_timezone()
                start_dt = timezone.make_aware(
                    datetime.datetime.combine(period_start, datetime.time.min),
                    tz,
                )
                end_dt = timezone.make_aware(
                    datetime.datetime.combine(period_end, datetime.time.max),
                    tz,
                )

                items = OrderItem.objects.filter(
                    order__status__in=cls.PAID_STATUSES,
                    order__created_at__range=(start_dt, end_dt),
                ).filter(
                    Q(product_variant__product__album__artist=artist)
                    | Q(product_variant__product__track__album__artist=artist)
                    | Q(product_variant__product__merch__artist=artist),
                )

                line_total_expression = Greatest(
                    F('unit_price') * F('quantity') - F('promocode_discount'),
                    Value(ZERO_MONEY),
                    output_field=DecimalField(
                        max_digits=MAX_PRICE_DIGITS,
                        decimal_places=MONEY_INTERNAL_PRECISION,
                    ),
                )

                data = items.aggregate(
                    orders_count=Count(
                        'order',
                        distinct=True,
                    ),
                    items_count=Coalesce(
                        Sum('quantity'),
                        0,
                    ),
                    gross_amount=Coalesce(
                        Sum(line_total_expression),
                        ZERO_MONEY,
                    ),
                    discount_amount=Coalesce(
                        Sum('promocode_discount'),
                        ZERO_MONEY,
                    ),
                    commission_amount=Coalesce(
                        Sum('platform_commission'),
                        ZERO_MONEY,
                    ),
                )

                delivery_amount = (
                    Order.objects
                    .filter(items__in=items)
                    .distinct()
                    .annotate(
                        artist_delivery=Cast(
                            KeyTextTransform(
                                'cost',
                                KeyTextTransform(
                                    str(artist.id),
                                    'delivery_calculation',
                                ),
                            ),
                            DecimalField(
                                max_digits=MAX_PRICE_DIGITS,
                                decimal_places=MONEY_INTERNAL_PRECISION,
                            ),
                        ),
                    )
                    .aggregate(
                        total=Coalesce(Sum('artist_delivery'), ZERO_MONEY),
                    )['total']
                )

                payout_amount = max(
                    data['gross_amount']
                    - data['commission_amount']
                    - delivery_amount,
                    ZERO_MONEY,
                )

                report, _ = Report.objects.update_or_create(
                    artist=artist,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                    defaults={
                        **data,
                        'delivery_amount': delivery_amount,
                        'payout_amount': payout_amount,
                        'status': Report.Status.READY,
                    },
                )

                return report
        except Exception as exc:
            logger.exception(
                'Генерация отчета якнулась на artist=%s period=%s—%s',
                artist.id,
                period_start,
                period_end,
            )
            Report.objects.update_or_create(
                artist=artist,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                defaults={
                    'status': Report.Status.FAILED,
                    'error_message': str(exc),
                },
            )
            raise
