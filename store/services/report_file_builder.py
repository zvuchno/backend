"""Генерация PDF-файла отчета о продажах артиста."""

import io
from pathlib import Path
from typing import Optional

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

from store.constants import ZERO_MONEY
from store.models import Report
from store.services.report import ReportService

FONT_DIR = Path(__file__).resolve().parent / 'fonts'
FONT_REGULAR = 'DejaVuSans'
FONT_BOLD = 'DejaVuSans-Bold'

pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(FONT_DIR / 'DejaVuSans.ttf')))
pdfmetrics.registerFont(
    TTFont(FONT_BOLD, str(FONT_DIR / 'DejaVuSans-Bold.ttf')),
)


class ReportFileBuilder:
    """Строит PDF-файл отчета на основе агрегированных данных Report."""

    TABLE_CELL_STYLE = ParagraphStyle(
        'TableCell',
        fontName=FONT_REGULAR,
        fontSize=7,
        wordWrap='CJK',
    )
    TABLE_CELL_RIGHT_STYLE = ParagraphStyle(
        'TableCellRight',
        parent=TABLE_CELL_STYLE,
        alignment=2,
    )

    @classmethod
    def build(cls, report: Report) -> io.BytesIO:
        """Формирует PDF-файл отчета и возвращает буфер с содержимым."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=5 * mm,
            rightMargin=5 * mm,
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
            spaceBefore=14,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            'ReportBody',
            fontName=FONT_REGULAR,
            fontSize=10,
        )
        elements = []
        elements.append(Paragraph('ZVUCHNO - Отчет о продажах', title_style))
        elements.append(
            Paragraph(
                f'Артист: {report.artist.name} (ID: {report.artist.id})',
                subtitle_style,
            ),
        )
        elements.append(
            Paragraph(
                f'Период: {report.period_start:%d.%m.%Y} '
                f'— {report.period_end:%d.%m.%Y}',
                subtitle_style,
            ),
        )
        elements.append(Spacer(1, 4))

        elements.append(Paragraph('Сводка', section_style))
        elements.append(cls._build_summary_table(report))

        elements.append(Paragraph('Детализация продаж', section_style))
        details_table = cls._build_details_table(report)
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
            ['Сумма доната, руб.', cls._fmt(report.donation_amount)],
            ['Сумма скидки, руб.', cls._fmt(report.discount_amount)],
            ['Продано товаров на сумму, руб.', cls._fmt(report.sales_amount)],
            ['Комиссия платформы, руб.', cls._fmt(report.commission_amount)],
            ['Стоимость доставки, руб.', cls._fmt(report.delivery_amount)],
            ['К выплате, руб.', cls._fmt(report.payout_amount)],
        ]
        table = Table(rows, colWidths=[100 * mm, 35 * mm], hAlign='LEFT')
        table.setStyle(cls._base_table_style(header_rows=1))
        table.setStyle(
            TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, -1), (-1, -1), FONT_BOLD),
                ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
            ]),
        )
        return table

    @classmethod
    def _build_details_table(
        cls,
        report: Report,
    ) -> Optional[Table]:
        items = (
            ReportService
            .get_report_items_queryset(
                artist=report.artist,
                period_start=report.period_start,
                period_end=report.period_end,
            )
            .select_related(
                'order',
                'product_variant__product',
            )
            .order_by('order__payments__created_at')
        )

        header_style = ParagraphStyle(
            'TableHeaderCell',
            parent=cls.TABLE_CELL_STYLE,
            fontName=FONT_BOLD,
            textColor=colors.white,
            alignment=1,
        )
        headers = [
            'Дата',
            '№ заказа',
            'SKU',
            'Товар',
            'Кол-во',
            'Цена',
            'Донат',
            'Скидка',
            'Сумма',
            'Промокод',
        ]
        rows = [[Paragraph(h, header_style) for h in headers]]
        has_rows = False

        for item in items.iterator(chunk_size=100):
            product_info = item.product_info or {}
            has_rows = True
            line_total = max(
                item.unit_price * item.quantity - item.promocode_discount,
                ZERO_MONEY,
            )
            rows.append([
                Paragraph(
                    item.order.created_at.strftime('%d.%m.%y'),
                    cls.TABLE_CELL_STYLE,
                ),
                Paragraph(str(item.order.order_number), cls.TABLE_CELL_STYLE),
                Paragraph(product_info.get('sku', ''), cls.TABLE_CELL_STYLE),
                Paragraph(
                    f'{product_info.get("kind", "")} '
                    f'{product_info.get("name", "")}',
                    cls.TABLE_CELL_STYLE,
                ),
                Paragraph(str(item.quantity), cls.TABLE_CELL_RIGHT_STYLE),
                Paragraph(
                    cls._fmt(item.price_at_purchase),
                    cls.TABLE_CELL_RIGHT_STYLE,
                ),
                Paragraph(cls._fmt(item.donation), cls.TABLE_CELL_RIGHT_STYLE),
                Paragraph(
                    cls._fmt(item.promocode_discount),
                    cls.TABLE_CELL_RIGHT_STYLE,
                ),
                Paragraph(cls._fmt(line_total), cls.TABLE_CELL_RIGHT_STYLE),
                Paragraph(
                    product_info.get('promocode', ''),
                    cls.TABLE_CELL_STYLE,
                ),
            ])

        if not has_rows:
            return None

        table = Table(
            rows,
            colWidths=[
                17 * mm,  # Дата
                24 * mm,  # № заказа
                26 * mm,  # sku
                84 * mm,  # Товар
                15 * mm,  # Кол-во
                20 * mm,  # Цена
                20 * mm,  # Донат
                20 * mm,  # Скидка
                20 * mm,  # Сумма
                38 * mm,  # Промокод
            ],
            hAlign='LEFT',
            repeatRows=1,
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
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            (
                'ROWBACKGROUNDS',
                (0, header_rows),
                (-1, -1),
                [colors.white, colors.HexColor('#F7F7F7')],
            ),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ])

    @staticmethod
    def _fmt(value) -> str:
        return f'{value:,.2f}'.replace(',', ' ').replace('.', ',')
