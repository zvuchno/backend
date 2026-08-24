"""Сервис формирования финансовых отчетов."""

import datetime
import logging
from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import (
    DecimalField,
    F,
    OuterRef,
    QuerySet,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone

from store.constants import (
    MAX_PRICE_DIGITS,
    MONEY_INTERNAL_PRECISION,
    ZERO_MONEY,
)
from store.models import OrderItem, Payment, Report

logger = logging.getLogger(__name__)

User = get_user_model()


class ReportService:
    """Сервис формирования финансовых отчетов получателей выплат."""

    @classmethod
    def generate(
        cls,
        *,
        payout_recipient: User,
        period_start: date,
        period_end: date,
    ) -> Report:
        """Формирует отчет получателю выплаты за отчетный период."""
        if period_start > period_end:
            raise ValueError('period_start должен быть <= period_end')
        try:
            with transaction.atomic():
                items = cls.get_report_items_queryset(
                    payout_recipient=payout_recipient,
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
                    sales_amount=Coalesce(
                        Sum(line_total_expression),
                        ZERO_MONEY,
                    ),
                    commission_amount=Coalesce(
                        Sum('platform_commission'),
                        ZERO_MONEY,
                    ),
                    discount_amount=Coalesce(
                        Sum('promocode_discount'),
                        ZERO_MONEY,
                    ),
                    donation_amount=Coalesce(
                        Sum(donation_expression),
                        ZERO_MONEY,
                    ),
                )

                payout_amount = max(
                    data['sales_amount'] - data['commission_amount'],
                    ZERO_MONEY,
                )

                report = Report.objects.filter(
                    payout_recipient=payout_recipient,
                    period_start=period_start,
                    period_end=period_end,
                ).first()

                if report and report.report_file:
                    report.report_file.delete(save=False)

                report, _ = Report.objects.update_or_create(
                    payout_recipient=payout_recipient,
                    period_start=period_start,
                    period_end=period_end,
                    defaults={
                        **data,
                        'payout_amount': payout_amount,
                        'status': Report.Status.PENDING,
                        'report_file': None,
                    },
                )
                return report
        except Exception:
            logger.exception(
                'Не удалось сформировать отчет '
                'payout_recipient=%s, period=%s—%s',
                payout_recipient.id,
                period_start,
                period_end,
            )
            raise

    @staticmethod
    def get_report_items_queryset(
        *,
        payout_recipient: User,
        period_start: date,
        period_end: date,
    ) -> QuerySet[OrderItem]:
        """Возвращает позиции оплаченных заказов за отчетный период."""
        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(
            datetime.datetime.combine(period_start, datetime.time.min),
            tz,
        )
        end_dt = timezone.make_aware(
            datetime.datetime.combine(period_end, datetime.time.max),
            tz,
        )
        successful_payment = Payment.objects.filter(
            order_id=OuterRef('order_id'),
            status=Payment.PaymentStatus.SUCCEEDED,
        ).order_by(
            'paid_at',
        )

        return OrderItem.objects.annotate(
            paid_at=Subquery(
                successful_payment.values('paid_at')[:1],
            ),
        ).filter(
            payout_recipient=payout_recipient,
            paid_at__range=(start_dt, end_dt),
        )
