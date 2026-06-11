"""Утилиты для работы с SQL view в миграциях.

SQL view храним не строками внутри миграций, а отдельными версионными
SQL-файлами:

    store/migrations/sql/views/<view_name>_v<version>.sql

Например:

    store/migrations/sql/views/listener_track_access_v1.sql
    store/migrations/sql/views/listener_album_access_v1.sql

Правила:
- SQL-файл должен содержать только CREATE VIEW ... AS ...
- DROP VIEW не пишем в SQL-файле, его добавляют helper-ы миграций.
- Новую view создаём через create_view().
- Изменение существующей view делаем через replace_view().
- Если view зависят друг от друга, сначала удаляем зависимые,
  потом базовые; создаём в обратном порядке: сначала базовые,
  потом зависимые.

Пример создания новой view:

    operations = [
        create_view('listener_album_access', version=1),
    ]

Пример замены view на новую версию:

    operations = [
        replace_view(
            view_name='listener_track_access',
            from_version=1,
            to_version=2,
        ),
    ]

Пример замены связанных view:

    operations = [
        replace_related_views([
            ('listener_track_access', 1, 2),
            ('listener_album_access', 1, 2),
        ]),
    ]

В списке связанных view порядок должен быть от базовой view к зависимой.
"""

from pathlib import Path

from django.db import migrations


MIGRATIONS_DIR = Path(__file__).resolve().parents[1]
SQL_VIEWS_DIR = MIGRATIONS_DIR / 'sql' / 'views'


def read_view_sql(view_name: str, version: int) -> str:
    """Читает SQL-файл указанной версии view.

    Ожидаемый путь:
        store/migrations/sql/views/<view_name>_v<version>.sql
    Например:
        read_view_sql('listener_album_access', 1)
    прочитает:
        store/migrations/sql/views/listener_album_access_v1.sql
    """
    path = SQL_VIEWS_DIR / f'{view_name}_v{version}.sql'
    return path.read_text(encoding='utf-8')


def drop_view(view_name: str) -> migrations.RunSQL:
    """Возвращает операцию удаления SQL view."""
    return migrations.RunSQL(
        sql=f'DROP VIEW IF EXISTS {view_name};',
        reverse_sql=migrations.RunSQL.noop,
    )


def create_view(view_name: str, version: int) -> migrations.RunSQL:
    """Создаёт SQL view из версионного SQL-файла.

    Используется, когда view появляется впервые.

    Пример:

        operations = [
            create_view('listener_album_access', version=1),
        ]

    SQL-файл должен содержать только CREATE VIEW.
    При откате миграции view будет удалена.
    """
    return migrations.RunSQL(
        sql=read_view_sql(view_name, version),
        reverse_sql=f'DROP VIEW IF EXISTS {view_name};',
    )


def replace_view(
    view_name: str,
    from_version: int,
    to_version: int,
) -> migrations.RunSQL:
    """Заменяет существующую SQL view на новую версию.

        Используется, когда меняется SQL существующей view.

        Пример:

            operations = [
                replace_view(
                    view_name='listener_track_access',
                    from_version=1,
                    to_version=2,
                ),
            ]

        При применении миграции:
        - удаляется текущая view;
        - создаётся view из файла новой версии.

        При откате:
        - удаляется новая view;
        - создаётся view из файла прошлой версии.
        """
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
    """Заменяет несколько связанных SQL view.

    Используется, когда нужно обновить базовую view и view, которые от неё
    зависят.

    View передаются в порядке от базовой к зависимой:

        [
            ('listener_track_access', 1, 2),
            ('listener_album_access', 1, 2),
        ]

    При применении миграции:
    - view удаляются в обратном порядке, чтобы сначала удалить зависимые;
    - view создаются в прямом порядке, чтобы сначала создать базовые.

    При откате используется тот же порядок удаления, но создаются прошлые
    версии SQL-файлов.

    Важно:
    SQL-файлы должны содержать только CREATE VIEW.
    DROP VIEW в SQL-файлы добавлять не нужно.
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
