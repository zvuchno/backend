from pathlib import Path

from django.db import migrations


MIGRATIONS_DIR = Path(__file__).resolve().parents[1]
SQL_VIEWS_DIR = MIGRATIONS_DIR / 'sql' / 'views'


def read_view_sql(view_name: str, version: int) -> str:
    """Читает SQL-файл версии view."""
    path = SQL_VIEWS_DIR / f'{view_name}_v{version}.sql'
    return path.read_text(encoding='utf-8')


def drop_view(view_name: str) -> migrations.RunSQL:
    """Возвращает операцию удаления SQL view."""
    return migrations.RunSQL(
        sql=f'DROP VIEW IF EXISTS {view_name};',
        reverse_sql=migrations.RunSQL.noop,
    )


def create_view(view_name: str, version: int) -> migrations.RunSQL:
    """Возвращает операцию создания SQL view из версионного файла."""
    return migrations.RunSQL(
        sql=read_view_sql(view_name, version),
        reverse_sql=f'DROP VIEW IF EXISTS {view_name};',
    )


def replace_view(
    view_name: str,
    from_version: int,
    to_version: int,
) -> migrations.RunSQL:
    """Заменяет SQL view с возможностью отката на прошлую версию."""
    return migrations.RunSQL(
        sql=(
            f'DROP VIEW IF EXISTS {view_name};\n'
            f'{read_view_sql(view_name, to_version)}'
        ),
        reverse_sql=(
            f'DROP VIEW IF EXISTS {view_name};\n'
            f'{read_view_sql(view_name, from_version)}'
        ),
    )


def replace_related_views(
    views: list[tuple[str, int, int]],
) -> migrations.RunSQL:
    """Заменяет связанные SQL view с возможностью отката.

    View передаются от базовой к зависимой.
    Например:
    [
        ('listener_track_access', 1, 2),
        ('listener_album_access', 1, 2),
    ]

    Удаляются в обратном порядке, создаются в прямом.
    """
    drop_sql = '\n'.join(
        f'DROP VIEW IF EXISTS {view_name};'
        for view_name, _from_version, _to_version in reversed(views)
    )
    create_sql = '\n'.join(
        read_view_sql(view_name, to_version)
        for view_name, _from_version, to_version in views
    )

    reverse_drop_sql = '\n'.join(
        f'DROP VIEW IF EXISTS {view_name};'
        for view_name, _from_version, _to_version in reversed(views)
    )
    reverse_create_sql = '\n'.join(
        read_view_sql(view_name, from_version)
        for view_name, from_version, _to_version in views
    )

    return migrations.RunSQL(
        sql=f'{drop_sql}\n{create_sql}',
        reverse_sql=f'{reverse_drop_sql}\n{reverse_create_sql}',
    )
