"""Таски генерации и рассылки финансовых отчетов артистов."""

import datetime
import logging

from celery import shared_task
from django.core.files.base import ContentFile
from django.db.models import Case, F, IntegerField, When
from django.utils import timezone

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
        ...


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
