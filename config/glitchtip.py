import logging
import os

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

SENSITIVE_KEYS = {
    'password',
    'new_password',
    'old_password',
    'retype_new_password',
    'token',
    'refresh',
    'access',
    'authorization',
    'cookie',
    'sessionid',
    'csrftoken',
    'uid',
    'phone',
    'email',
}


def scrub_sensitive_data(value):
    """Рекурсивно маскирует чувствительные данные в словарях и списках."""
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key in SENSITIVE_KEYS:
                value[key] = '[Filtered]'
            else:
                value[key] = scrub_sensitive_data(item)
        return value

    if isinstance(value, list):
        return [scrub_sensitive_data(item) for item in value]

    return value


def before_send(event, hint):
    """Очищает чувствительные данные перед отправкой события в GlitchTip."""
    request = event.get('request', {})

    if request.get('query_string'):
        request['query_string'] = '[Filtered]'

    if 'headers' in request:
        request['headers'] = scrub_sensitive_data(request['headers'])

    if 'data' in request:
        request['data'] = scrub_sensitive_data(request['data'])

    event['request'] = request
    return event


def get_traces_sample_rate() -> float:
    """Если в .env что-то неожиданное - не упадет."""
    value = os.getenv('GLITCHTIP_TRACES_RATE', '0.2')
    try:
        return float(value)
    except ValueError:
        return 0.2


def init_glitchtip():
    """Подключение GlitchTip для мониторинга ошибок проекта."""
    env = os.getenv('DJANGO_ENV', 'local')
    if env == 'local':
        return
    dsn = os.getenv('GLITCHTIP_DSN')
    if not dsn:
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        integrations=[
            DjangoIntegration(),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            ),
        ],
        before_send=before_send,
        send_default_pii=False,
        traces_sample_rate=get_traces_sample_rate(),
        auto_session_tracking=False,
    )
