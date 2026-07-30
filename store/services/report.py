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
    QuerySet,
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
from store.models import Order, OrderItem, Payment, Report
from users.models import ArtistProfile

logger = logging.getLogger(__name__)


class ReportService:
    """Сервис формирования агрегированных отчетов."""

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
                items = cls.get_report_items_queryset(
                    artist=artist,
                    period_start=period_start,
                    period_end=period_end,
                )
                line_total_expression = Greatest(
                    F('unit_price') * F('quantity') - F('promocode_discount'),
                    Value(ZERO_MONEY),
                    output_field=DecimalField(
                        max_digits=MAX_PRICE_DIGITS,
                        decimal_places=MONEY_INTERNAL_PRECISION,
                    ),
                )
                donation_expression = Greatest(
                    (F('unit_price') - F('price_at_purchase')) * F('quantity'),
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
                    sales_amount=Coalesce(
                        Sum(line_total_expression),
                        ZERO_MONEY,
                    ),
                    donation_amount=Coalesce(
                        Sum(donation_expression),
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
                    .filter(
                        id__in=items.values('order_id'),
                    )
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
                    data['sales_amount'] - data['commission_amount'],
                    ZERO_MONEY,
                )

                report = Report.objects.filter(
                    artist=artist,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                ).first()

                if report and report.report_file:
                    report.report_file.delete(save=False)

                report, _ = Report.objects.update_or_create(
                    artist=artist,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                    defaults={
                        **data,
                        'delivery_amount': delivery_amount,
                        'payout_amount': payout_amount,
                        'status': Report.Status.PENDING,
                        'report_file': None,
                    },
                )
                return report
        except Exception:
            logger.exception(
                'Не удалось сформировать отчет '
                'artist=%s, period_type=%s, period=%s—%s',
                artist.id,
                period_type,
                period_start,
                period_end,
            )
            raise

    @staticmethod
    def get_report_items_queryset(
        *,
        artist: ArtistProfile,
        period_start: date,
        period_end: date,
    ) -> QuerySet[OrderItem]:
        """Возвращает queryset товаров, входящих в финансовый отчет."""
        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(
            datetime.datetime.combine(period_start, datetime.time.min),
            tz,
        )
        end_dt = timezone.make_aware(
            datetime.datetime.combine(period_end, datetime.time.max),
            tz,
        )

        return (
            OrderItem.objects
            .filter(
                order__payments__status=Payment.PaymentStatus.SUCCEEDED,
                order__payments__paid_at__range=(start_dt, end_dt),
            )
            .filter(
                Q(product_variant__product__album__artist=artist)
                | Q(product_variant__product__track__album__artist=artist)
                | Q(product_variant__product__merch__artist=artist),
            )
            .distinct()
        )
