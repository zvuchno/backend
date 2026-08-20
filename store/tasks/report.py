"""Таски генерации и рассылки финансовых отчетов артистов."""

import datetime
import logging
import smtplib

from celery import shared_task
from django.core.files.base import ContentFile
from django.db.models import Case, F, IntegerField, When
from django.utils import timezone

from common.services.email import _send_template_email

from store.models import OrderItem, Payment, Product, Report
from store.services.report import ReportService
from store.services.report_file_builder import ReportFileBuilder
from users.models import ArtistProfile

logger = logging.getLogger(__name__)


def _artists_with_sales(period_start, period_end) -> set[int]:
    """Возвращает set id артистов с оплаченными продажами за период."""
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(
        datetime.datetime.combine(period_start, datetime.time.min),
        tz,
    )
    end_dt = timezone.make_aware(
        datetime.datetime.combine(period_end, datetime.time.max),
        tz,
    )

    artist_ids = (
        OrderItem.objects
        .filter(
            order__payments__status=Payment.PaymentStatus.SUCCEEDED,
            order__payments__paid_at__range=(start_dt, end_dt),
        )
        .annotate(
            artist_id=Case(
                When(
                    product_variant__product__product_type=Product.ProductType.ALBUM,
                    then=F('product_variant__product__album__artist_id'),
                ),
                When(
                    product_variant__product__product_type=Product.ProductType.TRACK,
                    then=F(
                        'product_variant__product__track__album__artist_id',
                    ),
                ),
                When(
                    product_variant__product__product_type=Product.ProductType.MERCH,
                    then=F('product_variant__product__merch__artist_id'),
                ),
                output_field=IntegerField(),
            ),
        )
        .values_list('artist_id', flat=True)
        .distinct()
    )

    return set(artist_ids)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def generate_report_task(
    self,
    artist_id,
    period_start,
    period_end,
    send_email=False,
):
    """Формирует отчет артиста и опционально отправляет его на почту."""
    try:
        report = ReportService.generate(
            artist=ArtistProfile.objects.get(id=artist_id),
            period_start=period_start,
            period_end=period_end,
        )

        buffer = ReportFileBuilder.build(report)
        filename = (
            f'report_{report.period_start:%Y_%m_%d}_'
            f'{report.period_end:%Y_%m_%d}.pdf'
        )
        report.report_file.save(
            filename,
            ContentFile(buffer.getvalue()),
            save=False,
        )
        report.status = Report.Status.READY
        report.save(update_fields=['report_file', 'status'])
    except (ValueError, ArtistProfile.DoesNotExist) as exc:
        logger.error(
            'Невозможно сформировать отчет artist=%s period=%s—%s: %s',
            artist_id,
            period_start,
            period_end,
            exc,
        )
        raise
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            Report.objects.filter(
                artist_id=artist_id,
                period_start=period_start,
                period_end=period_end,
            ).update(
                status=Report.Status.FAILED,
            )

            logger.exception(
                'Не удалось сформировать отчет после всех попыток '
                'artist_id=%s period=%s—%s',
                artist_id,
                period_start,
                period_end,
            )
            raise

        logger.warning(
            'Повтор генерации отчета artist_id=%s period=%s—%s, попытка %s/%s',
            artist_id,
            period_start,
            period_end,
            self.request.retries + 1,
            self.max_retries,
        )
        raise self.retry(exc=exc)

    logger.info(
        'Отчет id=%s сформирован: artist_id=%s period=%s—%s',
        report.id,
        artist_id,
        period_start,
        period_end,
    )

    if send_email:
        send_report_email_task.delay(report.id)


@shared_task
def dispatch_monthly_reports():
    """Запуск генерации месячных отчетов.

    Формирует отчеты за предыдущий календарный месяц
    для артистов, у которых были продажи за этот период.
    """
    today = timezone.localdate()

    period_end = today.replace(day=1) - datetime.timedelta(days=1)
    period_start = period_end.replace(day=1)

    artist_ids = _artists_with_sales(period_start, period_end)

    logger.info(
        'Запуск месячных отчетов за период %s — %s, артистов с продажами: %s',
        period_start,
        period_end,
        len(artist_ids),
    )

    for artist_id in artist_ids:
        generate_report_task.delay(
            artist_id=artist_id,
            period_start=period_start,
            period_end=period_end,
            send_email=True,
        )


@shared_task(
    bind=True,
    autoretry_for=(
        TimeoutError,
        OSError,
        smtplib.SMTPServerDisconnected,
    ),
    retry_backoff=30,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_report_email_task(self, report_id: int) -> None:
    """Отправляет сформированный отчет артиста по email."""
    report = Report.objects.select_related('artist__user').get(id=report_id)

    user = report.artist.user

    if user is None or not user.email:
        logger.warning(
            'Не удалось отправить отчет id=%s: у артиста нет email',
            report.id,
        )
        return

    if not report.report_file:
        raise ValueError(
            f'У отчета id={report.id} отсутствует файл',
        )

    filename = (
        f'report_{report.period_start:%Y_%m_%d}_'
        f'{report.period_end:%Y_%m_%d}.pdf'
    )

    with report.report_file.open('rb') as report_file:
        content = report_file.read()

    _send_template_email(
        subject=(f'Отчёт агента ЗВУЧНО за {report.period_start:%m.%Y}'),
        to_email=user.email,
        template_name='monthly_report',
        context={
            'artist': report.artist,
            'report': report,
        },
        attachments=[
            (
                filename,
                content,
                'application/pdf',
            ),
        ],
    )
