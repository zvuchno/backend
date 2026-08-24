"""Экспорт продаж артиста в CSV."""

import csv
import datetime

from django.db.models import OuterRef, QuerySet, Subquery
from django.http import HttpResponse
from django.utils import timezone

from common.access import managed_artist_q
from common.utils import format_document_money

from store.constants import ZERO_MONEY
from store.models import OrderItem, Payment


class SalesExportService:
    """Формирует CSV с детализацией продаж."""

    HEADERS = [
        'Дата/время',
        '№ заказа',
        'Артист',
        'Получатель выплаты',
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

    @staticmethod
    def get_sales_queryset(
        *,
        user,
        period_start,
        period_end,
    ) -> QuerySet[OrderItem]:
        """Возвращает продажи артистов за период."""
        tz = timezone.get_current_timezone()

        start_dt = timezone.make_aware(
            datetime.datetime.combine(
                period_start,
                datetime.time.min,
            ),
            tz,
        )
        end_dt = timezone.make_aware(
            datetime.datetime.combine(
                period_end,
                datetime.time.max,
            ),
            tz,
        )

        successful_payment = Payment.objects.filter(
            order_id=OuterRef('order_id'),
            status=Payment.PaymentStatus.SUCCEEDED,
        ).order_by('paid_at')

        return (
            OrderItem.objects
            .select_related(
                'order',
                'product_variant',
                'payout_recipient__artist_profile',
            )
            .annotate(
                paid_at=Subquery(
                    successful_payment.values('paid_at')[:1],
                ),
            )
            .filter(
                managed_artist_q(user),
                paid_at__range=(start_dt, end_dt),
            )
            .order_by('paid_at', 'order_id', 'id')
        )

    @classmethod
    def build_response(
        cls,
        *,
        user,
        period_start,
        period_end,
    ) -> HttpResponse:
        """Возвращает CSV-файл."""
        items = cls.get_sales_queryset(
            user=user,
            period_start=period_start,
            period_end=period_end,
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

            payout_recipient_profile = getattr(
                item.payout_recipient,
                'artist_profile',
                None,
            )
            payout_recipient_name = (
                payout_recipient_profile.name
                if payout_recipient_profile
                else item.payout_recipient.email
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
                payout_recipient_name,
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
                '',                                   # Получатель выплаты
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
