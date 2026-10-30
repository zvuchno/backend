"""Сервисные задачи восстановления производных данных."""

import datetime
import logging

from celery import shared_task
from django.db.models import Q

from store.models import (
    Album,
    Recording,
    Report,
    TrackGeneratedAudio,
)
from store.services.album_archive import AlbumArchiveScheduler
from store.services.audio import (
    TrackGeneratedAudioScheduler,
    calculate_file_hash,
)
from store.services.payout import PayoutService
from store.tasks.report import (
    generate_report_task,
    get_payout_recipients_with_sales,
)

logger = logging.getLogger(__name__)


@shared_task
def schedule_missing_track_audio() -> dict[str, int]:
    """Ставит в очередь отсутствующее или неуспешное аудио записей."""
    recordings = (
        Recording.objects
        .filter(audio_file__isnull=False)
        .exclude(audio_file='')
        .filter(
            Q(generated__isnull=True)
            | Q(
                generated__preview_status=(
                    TrackGeneratedAudio.ProcessingStatus.FAILED
                ),
            )
            | Q(
                generated__stream_status=(
                    TrackGeneratedAudio.ProcessingStatus.FAILED
                ),
            ),
        )
        .distinct()
    )

    candidates = recordings.count()

    for recording in recordings.iterator():
        TrackGeneratedAudioScheduler.schedule(recording)

    logger.info(
        'Найдено записей для подготовки аудио: %s.',
        candidates,
    )

    return {'candidates': candidates}


@shared_task
def backfill_missing_recording_hashes() -> dict[str, int]:
    """Заполняет SHA-256 для записей, у которых он ещё не рассчитан."""
    recordings = (
        Recording.objects
        .filter(file_hash='')
        .filter(audio_file__isnull=False)
        .exclude(audio_file='')
    )

    candidates = recordings.count()
    updated = 0
    skipped = 0
    errors = 0

    for recording in recordings.iterator():
        audio_file_name = recording.audio_file.name

        try:
            with recording.audio_file.open('rb') as source_file:
                file_hash = calculate_file_hash(source_file)
        except Exception:
            logger.exception(
                'Не удалось рассчитать SHA-256 записи %s.',
                recording.pk,
            )
            errors += 1
            continue

        updated_count = Recording.objects.filter(
            pk=recording.pk,
            audio_file=audio_file_name,
            file_hash='',
        ).update(
            file_hash=file_hash,
        )

        if updated_count:
            updated += 1
        else:
            skipped += 1

    return {
        'candidates': candidates,
        'updated': updated,
        'skipped': skipped,
        'errors': errors,
    }


@shared_task
def schedule_missing_album_archives() -> dict[str, int]:
    """Ставит в очередь отсутствующие или устаревшие архивы альбомов."""
    scheduled = 0

    albums = Album.objects.filter(
        is_published=True,
    )

    for album in albums.iterator():
        if AlbumArchiveScheduler.schedule(album):
            scheduled += 1

    logger.info(
        'Поставлено в очередь задач сборки архивов: %s.',
        scheduled,
    )

    return {'scheduled': scheduled}


@shared_task
def schedule_missing_reports(
    period_start: str,
    period_end: str,
) -> dict[str, int]:
    """Ставит в очередь отсутствующие отчеты за период."""
    period_start = datetime.date.fromisoformat(period_start)
    period_end = datetime.date.fromisoformat(period_end)

    recipient_ids = get_payout_recipients_with_sales(
        period_start,
        period_end,
    )

    existing_recipient_ids = set(
        Report.objects.filter(
            payout_recipient_id__in=recipient_ids,
            period_start=period_start,
            period_end=period_end,
            status__in=(
                Report.Status.PENDING,
                Report.Status.READY,
            ),
        ).values_list(
            'payout_recipient_id',
            flat=True,
        ),
    )

    missing_recipient_ids = recipient_ids - existing_recipient_ids

    for payout_recipient_id in missing_recipient_ids:
        generate_report_task.delay(
            payout_recipient_id=payout_recipient_id,
            period_start=period_start,
            period_end=period_end,
            notify=False,
        )

    logger.info(
        'Поставлено в очередь недостающих отчетов: %s.',
        len(missing_recipient_ids),
    )

    return {
        'scheduled': len(missing_recipient_ids),
    }


@shared_task
def create_missing_payouts() -> dict[str, int]:
    """Создает выплаты для готовых отчетов без выплаты."""
    reports = Report.objects.filter(
        status=Report.Status.READY,
        payout__isnull=True,
    ).select_related('payout_recipient')

    created = 0

    for report in reports.iterator():
        PayoutService.sync_with_report(report)
        created += 1

    logger.info(
        'Создано отсутствующих выплат: %s.',
        created,
    )

    return {'created': created}
