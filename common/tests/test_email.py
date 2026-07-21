from unittest.mock import patch

from common.services.email import send_template_email
from common.tasks.email import send_template_email_task


@patch('common.tasks.email.send_template_email_task.delay')
def test_send_template_email_enqueues_task(mock_delay):
    """Отправка шаблонного письма ставится в очередь."""
    send_template_email(
        subject='Тема',
        to_email='user@example.com',
        template_name='email_verification',
        context={'verification_url': 'https://example.com'},
    )

    mock_delay.assert_called_once_with(
        subject='Тема',
        to_email='user@example.com',
        template_name='email_verification',
        context={'verification_url': 'https://example.com'},
    )


@patch('common.tasks.email._send_template_email')
def test_send_template_email_task_sends_email(mock_send):
    """Задача выполняет непосредственную отправку письма."""
    send_template_email_task.run(
        subject='Тема',
        to_email='user@example.com',
        template_name='email_verification',
        context={'verification_url': 'https://example.com'},
    )

    mock_send.assert_called_once_with(
        subject='Тема',
        to_email='user@example.com',
        template_name='email_verification',
        context={'verification_url': 'https://example.com'},
    )
