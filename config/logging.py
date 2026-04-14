"""Конфигурация логирования проекта.

Модуль задает общие настройки logging для Django-приложения:
формат сообщений, обработчики, уровни логирования и правила
для логгеров проекта.

Как использовать в коде:
    import logging

    logger = logging.getLogger(__name__)

    logger.debug('Отладочное сообщение')
    logger.info('Событие бизнес-логики')
    logger.warning('Подозрительная, но ожидаемая ситуация')
    logger.error('Ошибка без traceback')
    logger.exception('Ошибка с traceback внутри except')

Основные правила:
    - В модулях проекта используйте logging.getLogger(__name__).
    - Желательно не настраивать handlers и formatters локально в рабочем коде.
    - Не логировать пароли, токены, cookie и другие секреты.
    - Не логируйте исключение в блоке except, если оно просто
      пробрасывается выше без добавления нового контекста.
    - logger.exception(...) используйте только внутри блока except.
"""

import os
from pathlib import Path

from django.conf import settings

LOG_DIR_NAME = 'logs'
LOG_FILENAME = 'log.log'
LOG_DIR = settings.BASE_DIR / LOG_DIR_NAME
LOG_FILE = LOG_DIR / LOG_FILENAME
LOG_FORMAT = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
LOG_LEVEL = 'DEBUG' if settings.DEBUG else 'INFO'
ROOT_HANDLERS = ['console']
if settings.DEBUG:
    ROOT_HANDLERS.append('file')

try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    # Устанавливаем права доступа для записи
    os.chmod(LOG_DIR, 0o755)
except Exception as e:
    print(f'Warning: Could not create log directory {LOG_DIR}: {e}')
    # Fallback к /tmp если не можем создать
    LOG_DIR = Path('/tmp/logs')
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE = LOG_DIR / LOG_FILENAME

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': LOG_FORMAT,
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOG_FILE),
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ROOT_HANDLERS,
        'level': LOG_LEVEL,
    },
    'loggers': {
        'users': {
            'level': LOG_LEVEL,
            'propagate': True,
        },
        'store': {
            'level': LOG_LEVEL,
            'propagate': True,
        },
        'django.request': {
            'level': 'ERROR',
            'propagate': True,
        },
    },
}
