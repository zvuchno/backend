"""Генерация PDF-файла отчета о продажах артиста."""

import datetime
import io
from pathlib import Path
from typing import Optional

from django.db.models import Q, QuerySet
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from store.models import Order, OrderItem, Report

FONT_DIR = Path(__file__).resolve().parent / 'fonts'
FONT_REGULAR = 'DejaVuSans'
FONT_BOLD = 'DejaVuSans-Bold'

pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(FONT_DIR / 'DejaVuSans.ttf')))
pdfmetrics.registerFont(
    TTFont(FONT_BOLD, str(FONT_DIR / 'DejaVuSans-Bold.ttf')),
)


class ReportFileBuilder:
    """Строит PDF-файл отчета на основе агрегированных данных Report."""

    PAID_STATUSES = (
        Order.Status.PAID,
        Order.Status.SHIPPED,
        Order.Status.COMPLETED,
    )

    @classmethod
    def build(cls, report: Report) -> io.BytesIO:
        """Формирует PDF-файл отчета и возвращает буфер с содержимым."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm,
        )

        base_styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=base_styles['Title'],
            fontName=FONT_BOLD,
            fontSize=16,
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=base_styles['Normal'],
            fontName=FONT_REGULAR,
            fontSize=10,
            textColor=colors.grey,
        )
        section_style = ParagraphStyle(
            'SectionHeader',
            parent=base_styles['Heading2'],
            fontName=FONT_BOLD,
            fontSize=12,
            spaceBefore=16,
            spaceAfter=8,
        )
        body_style = ParagraphStyle(
            'ReportBody',
            fontName=FONT_REGULAR,
            fontSize=10,
        )
        product_cell_style = ParagraphStyle(
            'ProductCell',
            fontName=FONT_REGULAR,
            fontSize=9,
        )

        elements = []
        elements.append(Paragraph('Отчет о продажах', title_style))
        elements.append(
            Paragraph(f'Артист: {report.artist.name}', subtitle_style),
        )
        elements.append(
            Paragraph(
                f'Период: {report.period_start:%d.%m.%Y} '
                f'— {report.period_end:%d.%m.%Y}',
                subtitle_style,
            ),
        )
        elements.append(Spacer(1, 12))

        elements.append(Paragraph('Сводка', section_style))
        elements.append(cls._build_summary_table(report))

        elements.append(Paragraph('Детализация продаж', section_style))
        details_table = cls._build_details_table(report, product_cell_style)
        if details_table is not None:
            elements.append(details_table)
        else:
            elements.append(Paragraph('За период продаж не было.', body_style))

        doc.build(elements)
        buffer.seek(0)
        return buffer

    @classmethod
    def _build_summary_table(cls, report: Report) -> Table:
        rows = [
            ['Показатель', 'Значение'],
            ['Количество заказов', str(report.orders_count)],
            ['Количество товаров', str(report.items_count)],
            ['Валовая выручка, руб.', cls._fmt(report.gross_amount)],
            ['Сумма скидок, руб.', cls._fmt(report.discount_amount)],
            ['Стоимость доставки, руб.', cls._fmt(report.delivery_amount)],
            ['Комиссия платформы, руб.', cls._fmt(report.commission_amount)],
            ['К выплате, руб.', cls._fmt(report.payout_amount)],
        ]
        table = Table(rows, colWidths=[100 * mm, 60 * mm], hAlign='LEFT')
        table.setStyle(cls._base_table_style(header_rows=1))
        # выделяем итоговую строку "К выплате"
        table.setStyle(
            TableStyle([
                ('FONTNAME', (0, -1), (-1, -1), FONT_BOLD),
                ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
            ]),
        )
        return table

    @classmethod
    def _build_details_table(
        cls,
        report: Report,
        product_cell_style: ParagraphStyle,
    ) -> Optional[Table]:
        items = (
            cls
            ._get_items_queryset(report)
            .select_related(
                'order',
                'product_variant__product',
            )
            .order_by('order__created_at')
        )

        rows = [
            ['Дата', '№ заказа', 'Товар', 'Кол-во', 'Цена', 'Скидка', 'Сумма'],
        ]
        has_rows = False
        for item in items.iterator():
            has_rows = True
            line_total = (
                item.unit_price * item.quantity - item.promocode_discount
            )
            rows.append([
                item.order.created_at.strftime('%d.%m.%Y'),
                str(item.order.id),
                Paragraph(
                    str(item.product_variant.product),
                    product_cell_style,
                ),
                str(item.quantity),
                cls._fmt(item.unit_price),
                cls._fmt(item.promocode_discount),
                cls._fmt(line_total),
            ])

        if not has_rows:
            return None

        table = Table(
            rows,
            colWidths=[
                25 * mm,  # Дата
                20 * mm,  # № заказа
                105 * mm,  # Товар
                18 * mm,  # Кол-во
                25 * mm,  # Цена
                30 * mm,  # Скидка
                34 * mm,  # Сумма
            ],
            hAlign='LEFT',
            repeatRows=1,  # заголовок повторяется на каждой странице
        )
        table.setStyle(cls._base_table_style(header_rows=1))
        return table

    @classmethod
    def _base_table_style(cls, header_rows: int) -> TableStyle:
        return TableStyle([
            (
                'BACKGROUND',
                (0, 0),
                (-1, header_rows - 1),
                colors.HexColor('#2E2E2E'),
            ),
            ('TEXTCOLOR', (0, 0), (-1, header_rows - 1), colors.white),
            ('FONTNAME', (0, 0), (-1, header_rows - 1), FONT_BOLD),
            ('FONTNAME', (0, header_rows), (-1, -1), FONT_REGULAR),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            (
                'ROWBACKGROUNDS',
                (0, header_rows),
                (-1, -1),
                [colors.white, colors.HexColor('#F7F7F7')],
            ),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ])

    @staticmethod
    def _fmt(value) -> str:
        return f'{value:,.2f}'.replace(',', ' ').replace('.', ',')

    @classmethod
    def _get_items_queryset(cls, report: Report) -> QuerySet[OrderItem]:
        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(
            datetime.datetime.combine(report.period_start, datetime.time.min),
            tz,
        )
        end_dt = timezone.make_aware(
            datetime.datetime.combine(report.period_end, datetime.time.max),
            tz,
        )

        return OrderItem.objects.filter(
            order__status__in=cls.PAID_STATUSES,
            order__created_at__range=(start_dt, end_dt),
        ).filter(
            Q(product_variant__product__album__artist=report.artist)
            | Q(product_variant__product__track__album__artist=report.artist)
            | Q(product_variant__product__merch__artist=report.artist),
        )
