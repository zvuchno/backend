"""Тесты отправки ежемесячных отчетов по email."""

import datetime

import pytest
from django.core import mail
from django.core.files.base import ContentFile

from store.models import Report
from store.tasks.report import (
    send_report_email_task,
)
from users.models import ArtistProfileType
from users.tests.factories import ArtistProfileFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def report():
    """Создает готовый отчет с PDF-файлом."""
    artist = ArtistProfileFactory(
        user__email='artist@example.com',
    )

    report = Report.objects.create(
        artist=artist,
        status=Report.Status.READY,
        period_start=datetime.date(2026, 7, 1),
        period_end=datetime.date(2026, 7, 31),
    )
    report.report_file.save(
        'report_2026_07_01_2026_07_31.pdf',
        ContentFile(b'%PDF-test-content'),
    )

    return report


class TestSendReportEmailTask:
    """Тесты отправки сформированного отчета."""

    def test_sends_report_to_artist_email(self, report):
        """Отчет отправляется на email артиста."""
        send_report_email_task.run(report.id)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ['artist@example.com']

    def test_email_has_expected_subject(self, report):
        """Письмо содержит тему с месяцем отчета."""
        send_report_email_task.run(report.id)

        message = mail.outbox[0]

        assert message.subject == ('Отчёт агента ЗВУЧНО за 07.2026')

    def test_email_contains_pdf_attachment(self, report):
        """PDF отчета прикладывается к письму."""
        send_report_email_task.run(report.id)

        message = mail.outbox[0]

        assert len(message.attachments) == 1

        attachment = message.attachments[0]

        assert attachment[0] == ('report_2026_07_01_2026_07_31.pdf')
        assert attachment[1] == b'%PDF-test-content'
        assert attachment[2] == 'application/pdf'

    def test_does_not_send_email_when_artist_has_no_account(self):
        """Отчет не отправляется артисту без аккаунта."""
        label = ArtistProfileFactory(
            profile_type=ArtistProfileType.LABEL,
        )
        artist = ArtistProfileFactory(
            user=None,
            label=label,
            profile_type=ArtistProfileType.ARTIST,
        )

        report = Report.objects.create(
            artist=artist,
            status=Report.Status.READY,
            period_start=datetime.date(2026, 7, 1),
            period_end=datetime.date(2026, 7, 31),
        )
        report.report_file.save(
            'report_2026_07_01_2026_07_31.pdf',
            ContentFile(b'%PDF-test-content'),
        )

        send_report_email_task.run(report.id)

        assert len(mail.outbox) == 0

    def test_does_not_send_email_when_user_has_no_email(self, report):
        """Отчет не отправляется при отсутствии email."""
        report.artist.user.email = ''
        report.artist.user.save(update_fields=['email'])

        send_report_email_task.run(report.id)

        assert len(mail.outbox) == 0

    def test_raises_error_when_report_file_is_missing(self, report):
        """Отправка невозможна без сформированного файла отчета."""
        report.report_file.delete(save=False)
        report.report_file = None
        report.save(update_fields=['report_file'])

        with pytest.raises(
            ValueError,
            match=f'У отчета id={report.id} отсутствует файл',
        ):
            send_report_email_task.run(report.id)
