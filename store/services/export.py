"""Экспорт продаж артиста в CSV."""

import csv

from django.http import HttpResponse

from common.utils import format_document_money

from store.constants import ZERO_MONEY
from store.services.report import ReportService


class SalesExportService:
    """Формирует CSV с детализацией продаж."""

    HEADERS = [
        'Дата/время',
        '№ заказа',
        'Артист',
        'Тип',
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
        payout_recipient,
        period_start,
        period_end,
    ) -> HttpResponse:
        """Возвращает CSV-файл."""
        items = (
            ReportService
            .get_report_items_queryset(
                payout_recipient=payout_recipient,
                period_start=period_start,
                period_end=period_end,
            )
            .select_related(
                'order',
                'product_variant',
            )
            .order_by('paid_at', 'order_id', 'id')
        )

        response = HttpResponse(
            content_type='text/csv; charset=utf-8',
        )
        response.write('\ufeff')
        response['Content-Disposition'] = (
            f'attachment; filename="sales_{period_start}_{period_end}.csv"'
        )

        writer = csv.writer(response, delimiter=';')
        writer.writerow(cls.HEADERS)

        # Переменные для накопления итогов
        total_quantity = 0
        total_discount = ZERO_MONEY
        total_donation = ZERO_MONEY
        total_commission = ZERO_MONEY
        total_payout = ZERO_MONEY

        for item in items:
            info = item.product_info or {}

            paid_at = (
                item.paid_at.strftime('%d.%m.%Y %H:%M') if item.paid_at else ''
            )
            product_type = (
                'цифровой'
                if item.product_variant.stock is None
                else 'физический'
            )

            payout = max(
                item.line_total - item.platform_commission,
                ZERO_MONEY,
            )

            # Накапливаем итоги
            total_quantity += item.quantity
            total_discount += item.promocode_discount
            total_donation += item.donation
            total_commission += item.platform_commission
            total_payout += payout

            writer.writerow([
                paid_at,
                item.order.order_number,
                info.get('artist_name', ''),
                product_type,
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

        if items:
            # fmt: off
            # Добавляем пустую строку-разделитель и итоговую строку
            writer.writerow([])
            writer.writerow([
                '',                                   # Дата/время
                '',                                   # № заказа
                '',                                   # Артист
                '',                                   # Тип
                'ИТОГО:',                             # Наименование
                '',                                   # SKU
                total_quantity,                       # Количество
                '',                                   # Цена
                '',                                   # Промокод
                format_document_money(total_discount),   # Скидка
                format_document_money(total_donation),   # Донат
                format_document_money(total_commission), # Комиссия площадки
                format_document_money(total_payout),     # Сумма к выплате
            ])
            # fmt: on

        return response
