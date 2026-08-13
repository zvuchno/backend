[![Main Zvuchno workflow](https://github.com/zvuchno/backend/actions/workflows/main.yml/badge.svg)](https://github.com/zvuchno/backend/actions/workflows/main.yml)
[![Website](https://img.shields.io/badge/Visit-Live%20Site-brightgreen)](https://dev.zvuchno.space/)

# Звучно — Backend

Backend API проекта **Звучно**.


## Стек

* Python 3.12
* Django 5.2
* Django REST Framework
* drf-spectacular (OpenAPI 3)
* Swagger UI / Redoc
* django-allauth
* SimpleJWT
* SQLite (для локального запуска без Docker)
* PostgreSQL 17 (Docker / production)
* Redis 7
* Celery
* Docker / Docker Compose
* Nginx
* Gunicorn
* GitHub Actions (CI/CD)
* pytest



Полный список зависимостей находится в:

* `requirements.txt` — локальная разработка и тестирование;
* `requirements.prod.txt` — production runtime.

---

# Быстрый старт

## 1. Клонировать репозиторий

```
mkdir zvuchno && cd zvuchno
git clone git@github.com:zvuchno/backend.git
cd backend
```

---

## 2. Создать виртуальное окружение

Linux / macOS

```
python3.12 -m venv .venv
source .venv/bin/activate
```

Windows

```
python -m venv venv
venv\Scripts\activate
```

---

## 3. Установить зависимости

```
pip install -r requirements.txt
```
```
pre-commit install
```
Команда pre-commit install создаст скрипт в .git/hooks/pre-commit, который будет вызывать pre-commit run при каждом git commit.
Можно запустить все хуки вручную (без коммита):
```
pre-commit run --all-files
```
Для утилиты pre-commit создан конфигурационный файл .pre-commit-config.yaml. Сначала запускаются стандартные хуки (проверки) из https://github.com/pre-commit/pre-commit-hooks. А потом запускаются хуки для ruff (https://github.com/astral-sh/ruff-pre-commit). Правила для ruff описаны в конфигурационном файле ruff.toml. Он сначала работает как линтер и исправляет ошибки, а потом как форматтер (автоматически форматирует код).


---

## 4. Настроить окружение
Создайте `.env` в корне проекта на основе `.env.example`.
Проект поддерживает два локальных сценария:

- запуск без Docker — Django запускается напрямую из виртуального окружения, по умолчанию можно использовать SQLite;
- запуск через Docker Compose — используется полное окружение с PostgreSQL, Redis, Celery и Nginx.
---

## 5. Применить миграции

```
python manage.py migrate
```

---

## 6. Создать суперпользователя

```
python manage.py createsuperuser
```

---

## 7. Запустить сервер

```
python manage.py runserver
```

Сервер будет доступен:

```
http://127.0.0.1:8000
```

Админка:

```
http://127.0.0.1:8000/admin
```
## Запуск через Docker

Docker Compose запускает полное локальное окружение:

* Django;
* PostgreSQL;
* Redis;
* Celery workers;
* Celery Beat;
* Flower;
* Nginx;
* bot.

Локальный backend запускается через Django `runserver`.

Для production используется отдельный `Dockerfile.prod`, в котором backend запускается через Gunicorn.

### Подготовка окружения

Создайте `.env` в корневой папке проекта на основе `.env.example`.

### Через Makefile

Для основных Docker-команд в проекте используется `Makefile`.

Посмотреть доступные команды:

```bash
make help
```

Собрать Docker image и запустить проект:

```bash
make up
```

Запустить проект в фоне:

```bash
make up-d
```

Если backend image уже собран и пересборка не требуется:

```bash
make start
```

или в фоне:

```bash
make start-d
```

После изменения `Dockerfile` или `requirements.txt`:

```bash
make build
```

Полностью пересобрать backend без Docker build cache и запустить в фоне:

```bash
make rebuild
```

Остановить контейнеры:

```bash
make down
```

Посмотреть логи:

```bash
make logs
```

### Напрямую через Docker Compose

`Makefile` является удобной обёрткой над Docker Compose. Команды можно выполнять и напрямую.

Собрать image:

```bash
docker compose build
```

Запустить проект:

```bash
docker compose up
```

или в фоне:

```bash
docker compose up -d
```

Подготовить базу данных и статику при первом запуске:

```bash
# Миграции
docker compose exec backend python manage.py migrate

# Сбор статических файлов
docker compose exec backend python manage.py collectstatic
```

Проект доступен по адресу: [http://localhost:8000](http://localhost:8000)

### Полезные команды Makefile

| Команда | Назначение                                      |
|---|-------------------------------------------------|
| `make help` | Показать доступные команды                      |
| `make up` | Собрать Docker image и запустить проект         |
| `make up-d` | Собрать Docker image и запустить проект в фоне  |
| `make start` | Запустить проект без пересборки                 |
| `make start-d` | Запустить проект без пересборки в фоне          |
| `make stop` | Остановить контейнеры без удаления |
| `make build` | Собрать Docker image                            |
| `make rebuild` | Пересобрать images без cache и запустить в фоне |
| `make down` | Остановить и удалить контейнеры                 |
| `make restart` | Перезапустить контейнеры                        |
| `make logs` | Следить за логами контейнеров                   |
| `make clean` | Удалить контейнеры и неиспользуемый build cache |
| `make shell` | Открыть Django shell                            |
| `make migrations` | Создать миграции                                |
| `make migrate` | Применить миграции                              |
| `make test` | Запустить тесты                                 |
| `make collectstatic` | Собрать статические файлы |

> [!NOTE]
> `make clean` не удаляет Docker volumes, поэтому локальная PostgreSQL база сохраняется.

### Мониторинг Celery через Flower

Flower используется для просмотра Celery worker и состояния фоновых задач.

Локально:

```text
http://localhost:5555/internal/flower/
```

На тестовом сервере:

```text
https://dev.zvuchno.space/internal/flower/
```

Доступ выполняется через Google OAuth. Необходимые переменные перечислены в `.env.example`.

После изменения переменных `FLOWER_*` контейнер необходимо пересоздать:

```bash
docker compose up -d --force-recreate flower
```

> [!NOTE]
> Сразу после запуска Flower при первом открытии worker иногда появляется ошибка `Unknown worker`. Обычно достаточно обновить страницу или открыть worker повторно через несколько секунд.

---

## Документация API доступна по следующим URL:

| URL | Назначение |
|-----|------------|
| `/api/docs/schema/` | JSON OpenAPI 3.0 (для генерации клиентов или проверки схемы) |
| `/api/docs/swagger/` | Swagger UI — интерактивная документация с возможностью тестирования эндпоинтов |
| `/api/docs/redoc/` | Redoc UI — удобная читаемая документация для разработчиков |

---

# Пользователь

В проекте используется кастомная модель пользователя:

```
users.CoreUser
```

В `settings.py`:

```
AUTH_USER_MODEL = "users.CoreUser"
```

---

# База данных

При локальном запуске без Docker может использоваться **SQLite**.
Файл базы (`db.sqlite3`) не хранится в репозитории.

При запуске через Docker Compose используется **PostgreSQL 17**.

Данные PostgreSQL хранятся в Docker volume `pg_data` и сохраняются между обычными остановками и пересозданием контейнеров.

> [!WARNING]
> Команда `docker compose down -v` удаляет volumes, включая локальную PostgreSQL базу.

---

# Полезные команды

Создать миграции:

```bash
python manage.py makemigrations
```

или в Docker:

```bash
make migrations
```

Применить миграции:

```bash
python manage.py migrate
```

или в Docker:

```bash
make migrate
```

Запустить shell:

```bash
python manage.py shell
```

или в Docker:

```bash
make shell
```

Запустить проверку Django:

```bash
python manage.py check
```

---

# Команды для ruff

Проверка и исправление ошибок в текущей директории:
```
ruff check --fix .
```
Проверка в текущей директории без исправлений (только отчёт об ошибках):
```
ruff check .
```
Демонстрация изменений в текущей директории в формате diff без записи в файлы:
```
ruff check --diff .
```
Автоматическое форматирование код в текущей директории:
```
ruff format .
```

# Тестирование

В проекте используется 'pytest' с плагином 'pytest-django'.

## Запуск всех тестов:
```
cd backend
pytest
```
или многопоточно (указать auto или подобрать количество потоков вручную):
```
pytest -n auto
```
Запуск внутри Docker:

```bash
make test
```

# Профилирование и оптимизация (Silk)

## Для отслеживания производительности API и выявления проблем N+1 в режиме разработки используется Django Silk
Как использовать:<br>
- Убедитесь, что в .env установлено DEBUG=True<br>
- Перейдите по адресу: http://localhost:8000/silk/<br>
- Сделайте запрос к интересующему эндпоинту (через Postman или Frontend)<br>
- В интерфейсе Silk выберите ваш запрос и откройте вкладку SQL<br>

На что обращать внимание:<br>
- Num. Queries: Если число запросов > 10–15 для простого списка, проверьте использование select_related и prefetch_related<br>
- Time: Длительные SQL-запросы (>100ms) могут сигнализировать об отсутствии индексов<br>
- Stack Trace: Silk показывает конкретную строку в сериализаторе или вьюхе, которая породила запрос<br>
> [!TIP]
> Перед началом замера новой фичи нажимайте иконку Clear в Silk, чтобы очистить старые логи и не раздувать базу данных.

## Дополнительно: N+1 (nplusone)<br>
Для быстрого обнаружения N+1 также используется nplusone

Как использовать:
- Запустите сервер (runserver)<br>
- Сделайте запрос к API<br>
- Проверьте предупреждения в консоли

На что обращать внимание:
- Potential n+1 query detected<br>
> [!TIP]
> nplusone показывает проблему сразу, а Silk помогает детально её проанализировать.

# Продакшен / Деплой
1. Создайте файл .env с переменными окружения и скопируйте его на сервер в директорию проекта - 'zvuchno'
2. Добавьте Secrets в GitHub Actions (Settings → Secrets and variables → Actions → New repository secret):
```
DOCKER_USERNAME  # Логин Docker Hub
DOCKER_PASSWORD  # Пароль или access token Docker Hub
SSH_HOST  # IP или домен сервера
SSH_USER  # Пользователь на сервере
SSH_KEY  # Приватный SSH ключ
SSH_PASSPHRASE  # Пароль от ключа (если он есть)
```

## Как запустить деплой через GitHub Actions

> [!NOTE]
> При пуше в ветку 'main' и 'develop' деплой запусается автоматически

### Вручную:
- Перейдите во вкладку Actions в репозитории
- В списке workflows выберите Main Zvuchno workflow
- Нажмите кнопку Run workflow

После этого GitHub запустит pipeline, который:
- соберёт Docker-образы
- отправит образы в Docker Hub
- выполнит деплой на сервер через SSH
