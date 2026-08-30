from django.db import migrations

from store.migrations.utils import create_materialized_view


CREATE_EXTENSION_SQL = """
CREATE EXTENSION IF NOT EXISTS pg_trgm;
"""


CREATE_INDEXES_SQL = """
CREATE UNIQUE INDEX catalog_search_id_idx
ON catalog_search (id);

CREATE UNIQUE INDEX catalog_search_entity_idx
ON catalog_search (entity_type, entity_id);

CREATE INDEX catalog_search_search_vector_idx
ON catalog_search
USING GIN (search_vector);

CREATE INDEX catalog_search_search_text_trgm_idx
ON catalog_search
USING GIN (search_text gin_trgm_ops);
"""


DROP_INDEXES_SQL = """
DROP INDEX IF EXISTS catalog_search_search_text_trgm_idx;
DROP INDEX IF EXISTS catalog_search_search_vector_idx;
DROP INDEX IF EXISTS catalog_search_entity_idx;
DROP INDEX IF EXISTS catalog_search_id_idx;
"""


def create_extension(apps, schema_editor):
    """Создаёт расширение pg_trgm на PostgreSQL."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute(CREATE_EXTENSION_SQL)


def create_indexes(apps, schema_editor):
    """Создаёт индексы materialized view на PostgreSQL."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute(CREATE_INDEXES_SQL)


def drop_indexes(apps, schema_editor):
    """Удаляет индексы materialized view на PostgreSQL."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute(DROP_INDEXES_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0052_alter_merch_options_alter_merchkind_options'),
    ]

    operations = [
        migrations.RunPython(
            create_extension,
            reverse_code=migrations.RunPython.noop,
        ),
        create_materialized_view(
            'catalog_search',
            version=1,
        ),
        migrations.RunPython(
            create_indexes,
            reverse_code=drop_indexes,
        ),
    ]
