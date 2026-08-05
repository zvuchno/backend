"""Генерация PDF-файла агентского отчета."""

import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
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

from common.utils import format_money

from store.models import Report
from store.services.report import ReportService
from users.models import ConsentDocument

FONT_DIR = Path(__file__).resolve().parent / 'fonts'
FONT_REGULAR = 'DejaVuSans'
FONT_BOLD = 'DejaVuSans-Bold'

pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(FONT_DIR / 'DejaVuSans.ttf')))
pdfmetrics.registerFont(
    TTFont(FONT_BOLD, str(FONT_DIR / 'DejaVuSans-Bold.ttf')),
)


class ReportFileBuilder:
    """Строит PDF агентского отчета."""

    TABLE_CELL_STYLE = ParagraphStyle(
        'TableCell',
        fontName=FONT_REGULAR,
        fontSize=8,
        leading=10,
    )
    TABLE_CELL_RIGHT_STYLE = ParagraphStyle(
        'TableCellRight',
        parent=TABLE_CELL_STYLE,
        alignment=2,
    )

    @classmethod
    def build(cls, report: Report) -> io.BytesIO:
        """Формирует PDF-файл отчета."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'Title',
            parent=styles['Title'],
            fontName=FONT_BOLD,
            fontSize=10,
            leading=13,
            alignment=1,
            spaceAfter=0,
        )
        body_style = ParagraphStyle(
            'Body',
            fontName=FONT_REGULAR,
            fontSize=10,
            leading=14,
        )
        section_style = ParagraphStyle(
            'Section',
            parent=body_style,
            fontName=FONT_BOLD,
            spaceAfter=3,
        )
        justify_body_style = ParagraphStyle(
            'JustifyBody',
            parent=body_style,
            alignment=4,
            leftIndent=0,
            rightIndent=0,
        )

        elements = []

        report_date = report.updated_at.strftime('%d.%m.%Y')
        offer = ConsentDocument.objects.filter(
            document_type=ConsentDocument.DocumentType.ARTIST_OFFER,
            is_active=True,
        ).first()
        agreement_date = (
            offer.created_at.strftime('%d.%m.%Y')
            if offer and offer.created_at
            else ''
        )
        artist_status, principal = cls._get_principal(report)

        elements.append(
            Paragraph(
                (
                    f'Отчет агента от {report_date} '
                    'об исполнении агентского поручения'
                ),
                ParagraphStyle('T1', parent=title_style, spaceAfter=0),
            ),
        )

        elements.append(
            Paragraph(
                f'по Агентскому договору-оферте от {agreement_date}',
                ParagraphStyle(
                    'T2',
                    parent=body_style,
                    alignment=1,
                    spaceBefore=0,
                ),
            ),
        )

        elements.append(Spacer(1, 8))

        elements.append(
            Paragraph(
                ('Маркетплейс (агент): ИП Переведенцев Антон Андреевич'),
                section_style,
            ),
        )

        elements.append(
            Paragraph(
                (f'Продавец (принципал): {artist_status} {principal}'),
                section_style,
            ),
        )

        elements.append(Spacer(1, 10))

        def make_list_item(
            num: str,
            text: str,
            style,
            col_width_num=8 * mm,
        ) -> Table:
            """Создает строку списка с фиксированным отступом."""
            return Table(
                [
                    [
                        Paragraph(num, style),
                        Paragraph(text, style),
                    ],
                ],
                colWidths=[col_width_num, None],
                style=[
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
                ],
            )

        elements.append(
            make_list_item(
                '1.',
                'Маркетплейсом совершены действия по приему платежей от '
                'покупателей, являющихся оплатой цены Товаров (Мерча или '
                'Цифрового контента) в соответствии с Договором-офертой.',
                justify_body_style,
            ),
        )

        elements.append(
            make_list_item(
                '2.',
                f'Агентское вознаграждение Маркетплейса по '
                'данному отчету за отчетный период: '
                f'{report.period_start:%m.%Y} составляет '
                f'{format_money(report.commission_amount)} рублей.',
                justify_body_style,
            ),
        )

        elements.append(
            make_list_item(
                '3.',
                'Расшифровка платежей за Отчетный период:',
                justify_body_style,
            ),
        )

        elements.append(
            Paragraph(
                'руб.',
                ParagraphStyle(
                    'CurrencyLabel',
                    parent=cls.TABLE_CELL_STYLE,
                    alignment=2,
                    spaceAfter=2,
                ),
            ),
        )

        elements.append(cls._build_payment_table(report))

        elements.append(Spacer(1, 18))

        elements.append(
            Paragraph(
                'Детализация информации о проданных Товарах:',
                body_style,
            ),
        )

        elements.append(Spacer(1, 6))
        details = cls._build_details_table(report)

        if details:
            elements.append(details)

        elements.append(Spacer(1, 10))

        elements.append(
            Paragraph(
                (f'Итого: {format_money(report.sales_amount)} руб.'),
                body_style,
            ),
        )

        elements.append(Spacer(1, 10))

        elements.append(
            Paragraph(
                (
                    'Поручение считается исполненным Маркетплейсом '
                    'надлежащим образом и принятым Продавцом '
                    'в указанном Отчете объеме, если в течение '
                    '3 календарных дней от Продавца не поступило '
                    'мотивированных письменных возражений '
                    'на адрес электронной почты Маркетплейса.'
                ),
                justify_body_style,
            ),
        )

        doc.build(elements)
        buffer.seek(0)
        return buffer

    @classmethod
    def _build_payment_table(cls, report: Report) -> Table:
        """Таблица расчетов."""
        left_style = cls.TABLE_CELL_STYLE
        right_style = cls.TABLE_CELL_RIGHT_STYLE

        rows = [
            [
                Paragraph(
                    'Получено от покупателей в адрес Продавца '
                    'в счет заключенных договоров',
                    left_style,
                ),
                Paragraph(format_money(report.sales_amount), right_style),
            ],
            [
                Paragraph('Возвращено платежей покупателям', left_style),
                Paragraph('0.00', right_style),
            ],
            [
                Paragraph('Подлежит удержанию Маркетплейсом', left_style),
                Paragraph(format_money(report.commission_amount), right_style),
            ],
            [
                Paragraph(
                    '&nbsp;&nbsp;- агентское вознаграждение',
                    left_style,
                ),
                Paragraph(format_money(report.commission_amount), right_style),
            ],
            [
                Paragraph(
                    '&nbsp;&nbsp;- расходы, связанные с исполнением поручения',
                    left_style,
                ),
                Paragraph('0.00', right_style),
            ],
            [
                Paragraph(
                    '&nbsp;&nbsp;- возвраты платежей покупателям',
                    left_style,
                ),
                Paragraph('0.00', right_style),
            ],
            [
                Paragraph(
                    'Подлежит перечислению Маркетплейсом на счет Продавца',
                    left_style,
                ),
                Paragraph(format_money(report.payout_amount), right_style),
            ],
        ]

        table = Table(
            rows,
            colWidths=[
                135 * mm,
                35 * mm,
            ],
        )

        table.setStyle(
            cls._base_table_style(),
        )

        return table

    @classmethod
    def _build_details_table(
        cls,
        report: Report,
    ) -> Table | None:
        """Детализация проданных товаров."""
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
            .order_by('order__payments__paid_at')
        )
        if not items.exists():
            return None

        header_style = ParagraphStyle(
            'DetailsHeaderStyle',
            parent=cls.TABLE_CELL_STYLE,
            fontName=FONT_REGULAR,
            fontSize=8,
            leading=10,
            alignment=1,
        )

        cell_center = ParagraphStyle(
            'DetailsCellCenter',
            parent=cls.TABLE_CELL_STYLE,
            alignment=1,
        )
        cell_left = ParagraphStyle(
            'DetailsCellLeft',
            parent=cls.TABLE_CELL_STYLE,
            alignment=0,
            wordWrap='CJK',
        )
        cell_right = ParagraphStyle(
            'DetailsCellRight',
            parent=cls.TABLE_CELL_STYLE,
            alignment=2,
        )

        rows = [
            [
                Paragraph('№', header_style),
                Paragraph(
                    'Наименование<br/>проданного<br/>товара',
                    header_style,
                ),
                Paragraph(
                    'Количество<br/>проданного<br/>товара',
                    header_style,
                ),
                Paragraph('Цена товара', header_style),
                Paragraph('Стоимость', header_style),
            ],
        ]

        for idx, item in enumerate(items, start=1):
            product_info = item.product_info or {}
            price = item.line_total / item.quantity

            rows.append([
                Paragraph(str(idx), cell_center),
                Paragraph(
                    (
                        f'{product_info.get("kind", "")} '
                        f'{product_info.get("name", "")}'
                    ).strip(),
                    cell_left,
                ),
                Paragraph(str(item.quantity), cell_center),
                Paragraph(format_money(price), cell_right),
                Paragraph(format_money(item.line_total), cell_right),
            ])

        # в сумме 170 мм
        table = Table(
            rows,
            colWidths=[
                10 * mm,
                75 * mm,
                25 * mm,
                30 * mm,
                30 * mm,
            ],
            hAlign='CENTER',
            repeatRows=1,
        )

        table.setStyle(
            TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), FONT_REGULAR),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ]),
        )

        return table

    @staticmethod
    def _base_table_style() -> TableStyle:
        return TableStyle(
            [
                (
                    'VALIGN',
                    (0, 0),
                    (-1, -1),
                    'MIDDLE',
                ),
                (
                    'GRID',
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.black,
                ),
                (
                    'TOPPADDING',
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    'BOTTOMPADDING',
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ],
        )

    @staticmethod
    def _get_principal(
        report,
    ) -> tuple[str, str]:
        """Возвращает статус и наименование принципала."""
        legal_profile = getattr(
            report.artist.user,
            'legal_profile',
            None,
        )

        if legal_profile is None:
            return '', report.artist.name

        recipient_type = legal_profile.recipient_type
        artist_status = legal_profile.get_recipient_type_display()

        if recipient_type == legal_profile.RecipientType.LEGAL_ENTITY:
            company_data = getattr(
                legal_profile,
                'company_data',
                None,
            )

            principal = (
                company_data.company_name
                if company_data and company_data.company_name
                else report.artist.name
            )

            return artist_status, principal

        identity_data = getattr(
            legal_profile,
            'identity_data',
            None,
        )

        if identity_data is None:
            return artist_status, report.artist.name

        principal = ' '.join(
            part
            for part in (
                identity_data.last_name,
                identity_data.first_name,
                identity_data.middle_name,
            )
            if part
        )

        return artist_status, principal or report.artist.name
