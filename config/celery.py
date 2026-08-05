import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

CELERY_BEAT_SCHEDULE = {
    'cleanup-expired-track-uploads': {
        'task': 'store.tasks.track_upload.cleanup_expired_track_uploads',
        'schedule': crontab(hour=4, minute=10),
    },
    'release-expired-reservations': {
        'task': 'store.tasks.reservations.release_expired_reservations',
        'schedule': crontab(minute='*/10'),
    },
    'dispatch-daily-reports': {
        'task': 'store.tasks.report.dispatch_daily_reports',
        'schedule': crontab(hour=4, minute=0),
    },
    'dispatch-monthly-reports': {
        'task': 'store.tasks.report.dispatch_monthly_reports',
        'schedule': crontab(day_of_month=1, hour=5, minute=0),
    },
    'flush-expired-jwt-tokens': {
        'task': 'common.tasks.token_blacklist.flush_expired_tokens',
        'schedule': crontab(hour=2, minute=0),
    },
}

app.conf.beat_schedule = CELERY_BEAT_SCHEDULE
