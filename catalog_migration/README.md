# Разовая миграция каталога

`catalog_migration` импортирует подготовленный каталог в create-only режиме:
профили, релизы, треки, мерч, цифровые товары, публичные сведения, изображения
и аудио. Повторный запуск обязан быть идемпотентным: уже сопоставленные объекты
не создаются и не перезаписываются.

## Данные пакета

Реальные bundle, конфигурация импорта, CSV, manifest, media и отчёты не входят
в репозиторий. Они передаются отдельно и монтируются read-only либо хранятся в
приватном S3. Ожидаемая структура v2:

```text
migration-v2/
  import_config.json
  artist_codes.json
  artist_slug_overrides.json
  public_contacts.json          # только если этап включён
  zvuchno-migration-bundle-v2/
    bundle.json
    data/*.json
    schema/*.json
    reference/*.json
    media/manifests/*.json
    media/audio/originals/*
    media/images/*
```

Минимальный синтетический пример `import_config.json`:

```json
{
  "schema_version": 1,
  "bundle_version": "2.0",
  "artist_code_whitelist": ["TEST"],
  "enabled": {
    "profiles": true,
    "releases": true,
    "tracks": true,
    "merch": true,
    "public_contacts": true,
    "telegram": false,
    "cdek": false
  }
}
```

Значения whitelist и переключателей определяются для конкретного переноса во
внешнем файле. Реальный пример JSON в Git намеренно отсутствует.

## Реестр и состояние

Несмотря на имя класса, `CatalogMigrationRegistry` не является JSON-файлом.
Единый реестр соответствий хранится в PostgreSQL в
`CatalogMigrationMapping`; namespace v2 привязан к SHA-256 `bundle.json`.
Возобновляемое состояние аудио хранится в `CatalogMigrationAudioState`.
`import_state.json` текущим runtime не читается и не должен создаваться.

## Проверка и запуск

Локальный режим читает весь пакет с диска и пишет в штатные Django media
storages:

```bash
USE_S3_MEDIA=False python manage.py preflight_catalog_migration /path/migration-v2
USE_S3_MEDIA=False python manage.py import_catalog /path/migration-v2 --dry-run
USE_S3_MEDIA=False python manage.py import_catalog /path/migration-v2
```

При `USE_S3_MEDIA=True` единая команда получает из приватного bucket только
конфигурацию, JSON schemas/data и manifests. Оригиналы остаются в S3 и читаются
существующими image/audio сервисами по мере импорта:

```bash
USE_S3_MEDIA=True python manage.py import_catalog \
  --s3-prefix migration-v2 --dry-run
USE_S3_MEDIA=True python manage.py import_catalog \
  --s3-prefix migration-v2
```

Единый `--dry-run` проверяет внешний пакет и полный preflight, не создавая
объекты и не ставя Celery-задачи. Импорт останавливается на первой ошибке;
после устранения причины команда запускается повторно.

`--retry-errors` повторяет только явно ошибочные аудиосостояния. Уже стоящие в
broker `QUEUED/PROCESSING` задачи повторно не публикуются:

```bash
python manage.py import_catalog /path/migration-v2 --retry-errors
```

Для обычной сервисной догенерации отсутствующих или `FAILED`
preview/stream существует Celery-задача
`store.tasks.maintenance.schedule_missing_track_audio`. Её запускают
отдельно от importer после проверки worker/broker; она не заменяет
`--retry-errors` для согласования `CatalogMigrationAudioState`.

## Порядок production migration

1. Проверить backup и настройки PostgreSQL, Redis, media storage и worker
   очереди `media`.
2. Выполнить `--dry-run` и изучить preflight.
3. Запустить media worker, затем `import_catalog`.
4. Дождаться завершения Celery-задач. Постановка задач не означает готовность
   preview/stream.
5. Проверить числа `CatalogMigrationMapping`, `CatalogMigrationAudioState`,
   `TrackUpload`, оригиналов и `TrackGeneratedAudio`, а также отсутствие
   неожиданной публикации.
6. Для явных `FAILED` устранить причину и использовать `--retry-errors`.
   Повторная задача для уже готового актуального original является no-op;
   настоящий replace original переводит generated audio в `PENDING` и
   пересобирает его.
7. Повторить обычный импорт для итоговой идемпотентной сверки.

## Завершение и удаление временных таблиц

Перед откатом временных migration-моделей необходимо:

- создать и проверить backup PostgreSQL;
- остановить importer и убедиться, что он больше не запускается;
- дождаться всех связанных Celery-задач и проверить отсутствие активной
  обработки;
- записать фактическую предыдущую миграцию из migration graph, не угадывая её
  имя.



В текущей реализации временные модели исторически добавлены миграциями
`store/0058` и `store/0059`, поэтому до переноса ownership эквивалентная
операция выполняется с app label `store`:

```bash
python manage.py showmigrations store
python manage.py migrate store <previous_migration>
```

После отката нужно проверить через PostgreSQL catalog, что таблицы mappings и
audio state действительно удалены. Только затем production deployment можно
возвращать на обычную prod/main ветку, где временных моделей и importer нет.
