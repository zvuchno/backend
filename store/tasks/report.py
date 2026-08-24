"""Таски генерации и рассылки финансовых отчетов артистов."""

import datetime
import logging
import smtplib

from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone

from common.services.email import _send_template_email

from store.models import OrderItem, Payment, Report
from store.services.report import ReportService
from store.services.report_file_builder import ReportFileBuilder

logger = logging.getLogger(__name__)

User = get_user_model()


def _payout_recipients_with_sales(period_start, period_end) -> set[int]:
    """Возвращает set id получателей с оплаченными продажами за период."""
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(
        datetime.datetime.combine(period_start, datetime.time.min),
        tz,
    )
    end_dt = timezone.make_aware(
        datetime.datetime.combine(period_end, datetime.time.max),
        tz,
    )

    payout_recipient_ids = (
        OrderItem.objects
        .filter(
            order__payments__status=Payment.PaymentStatus.SUCCEEDED,
            order__payments__paid_at__range=(start_dt, end_dt),
        )
        .values_list('payout_recipient_id', flat=True)
        .distinct()
    )

    return set(payout_recipient_ids)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def generate_report_task(
    self,
    payout_recipient_id,
    period_start,
    period_end,
    send_email=False,
):
    """Формирует отчет получателя и опционально отправляет его на почту."""
    try:
        report = ReportService.generate(
            payout_recipient=User.objects.get(id=payout_recipient_id),
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
    except (ValueError, User.DoesNotExist) as exc:
        logger.error(
            'Невозможно сформировать отчет '
            'payout_recipient_id=%s period=%s—%s: %s',
            payout_recipient_id,
            period_start,
            period_end,
            exc,
        )
        raise
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            Report.objects.filter(
                payout_recipient_id=payout_recipient_id,
                period_start=period_start,
                period_end=period_end,
            ).update(
                status=Report.Status.FAILED,
            )

            logger.exception(
                'Не удалось сформировать отчет после всех попыток '
                'payout_recipient_id=%s period=%s—%s',
                payout_recipient_id,
                period_start,
                period_end,
            )
            raise

        logger.warning(
            'Повтор генерации отчета '
            'payout_recipient_id=%s period=%s—%s, попытка %s/%s',
            payout_recipient_id,
            period_start,
            period_end,
            self.request.retries + 1,
            self.max_retries,
        )
        raise self.retry(exc=exc)

    logger.info(
        'Отчет id=%s сформирован: payout_recipient_id=%s period=%s—%s',
        report.id,
        payout_recipient_id,
        period_start,
        period_end,
    )

    if send_email:
        send_report_email_task.delay(report.id)


@shared_task
def dispatch_monthly_reports():
    """Запуск генерации месячных отчетов.

    Формирует отчеты за предыдущий календарный месяц
    для получателей, у которых были продажи за этот период.
    """
    today = timezone.localdate()

    period_end = today.replace(day=1) - datetime.timedelta(days=1)
    period_start = period_end.replace(day=1)

    payout_recipient_ids = _payout_recipients_with_sales(
        period_start,
        period_end,
    )

    logger.info(
        'Запуск месячных отчетов за период'
        ' %s — %s, получателей выплат с продажами: %s',
        period_start,
        period_end,
        len(payout_recipient_ids),
    )

    for payout_recipient_id in payout_recipient_ids:
        generate_report_task.delay(
            payout_recipient_id=payout_recipient_id,
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
    report = Report.objects.select_related(
        'payout_recipient__artist_profile',
    ).get(id=report_id)

    user = report.payout_recipient
    payout_recipient_profile = user.artist_profile

    if not user.email:
        logger.warning(
            'Не удалось отправить отчет id=%s: у получателя выплаты нет email',
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
            'payout_recipient_profile': payout_recipient_profile,
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
