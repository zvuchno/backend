"""Схемы автодокументации OpenAPI для сущности юридических документов.

Содержит конфигурации `drf-spectacular` для валидного отображения
операций в Swagger/ReDoc.
"""

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)

CONSENT_DOC_TAGS = ['Compliance']


consent_doc_schema = extend_schema_view(
    list=extend_schema(
        summary='Список документов',
        description=(
            'Возвращает список юридических документов. '
            'Для каждого типа возвращается актуальная активная версия.'
        ),
        tags=CONSENT_DOC_TAGS,
    ),
    retrieve=extend_schema(
        summary='Получить документ',
        description=(
            'Возвращает актуальный юридический документ для выбранного '
            'типа (по slug). '
            'Каждый тип документа имеет только одну активную версию.'
        ),
        tags=CONSENT_DOC_TAGS,
    ),
)
