"""Экспорт продаж артиста в CSV."""

import csv

from django.http import HttpResponse

from common.utils import format_document_money

from store.constants import ZERO_MONEY
from store.services.report import ReportService


class SalesExportService:
    """Формирует CSV с детализацией продаж."""

    HEADERS = [
        'Дата',
        '№ заказа',
        'Артист',
        'Наименование',
        'SKU',
        'Количество',
        'Цена',
        'Промокод',
        'Скидка',
        'Донат',
        'Комиссия площадки',
        'Сумма к выплате',
    ]

    @classmethod
    def build_response(
        cls,
        *,
        artist,
        period_start,
        period_end,
    ) -> HttpResponse:
        """Возвращает CSV-файл."""
        items = (
            ReportService
            .get_report_items_queryset(
                artist=artist,
                period_start=period_start,
                period_end=period_end,
            )
            .select_related(
                'order',
                'product_variant__product',
            )
            .prefetch_related('order__payments')
            .order_by('paid_at', 'order_id', 'id')
        )

        response = HttpResponse(
            content_type='text/csv; charset=utf-8-sig',
        )
        response['Content-Disposition'] = (
            f'attachment; filename="sales_{period_start}_{period_end}.csv"'
        )

        writer = csv.writer(response, delimiter=';')
        writer.writerow(cls.HEADERS)

        for item in items:
            info = item.product_info or {}

            paid_at = (
                item.paid_at.strftime('%d.%m.%Y %H:%M') if item.paid_at else ''
            )

            payout = max(
                item.line_total - item.platform_commission,
                ZERO_MONEY,
            )

            writer.writerow([
                paid_at,
                item.order.order_number,
                info.get('artist_name', ''),
                f'{info.get("kind", "")} {info.get("name", "")}',
                info.get('sku', ''),
                item.quantity,
                format_document_money(item.price_at_purchase),
                info.get('promocode', ''),
                format_document_money(item.promocode_discount),
                format_document_money(item.donation),
                format_document_money(item.platform_commission),
                format_document_money(payout),
            ])

        return response
