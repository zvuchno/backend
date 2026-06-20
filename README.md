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
* SQLite (для локальной разработки)
* PostgreSQL
* Docker / Docker Compose
* Nginx
* Gunicorn
* GitHub Actions (CI/CD)
* pytest



Основные зависимости:

```
Django==5.2.12
djangorestframework==3.16.1
django-allauth==65.14.3
djangorestframework_simplejwt==5.5.1
django-filter==25.2
ruff==0.15.5
```

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

## 4. .env файл
Пример - env.example

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
### Запуск через Docker

Этот метод запускает полную связку: Django + PostgreSQL + Gunicorn + Nginx.

**Подготовьте окружение:**

Создайте файл .env в корневой папке проекта на основе примера: env.example

Соберите и запустите контейнеры:
```
docker compose up --build
```
Подготовьте базу данных и статику при первом запуске:
```
# Миграции
docker compose exec backend python manage.py migrate
# Сбор статических файлов
docker compose exec backend python manage.py collectstatic
```
Проект доступен по адресу: [http://localhost:8000](http://localhost:8000)

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

При работе с пользователем используйте:

```python
from django.contrib.auth import get_user_model

User = get_user_model()
```

---

# База данных

Для локальной разработки используется **SQLite**.

Файл базы (`db.sqlite3`) не хранится в репозитории.

После клонирования проекта выполните:

```
python manage.py migrate
```

---

# Полезные команды

Создать миграции:

```
python manage.py makemigrations
```

Применить миграции:

```
python manage.py migrate
```

Запустить shell:

```
python manage.py shell
```

Запустить проверку:

```
python manage.py check
```

## Импорт тестового контента

В репозитории есть два способа импортировать тестовый контент:

* локальная Django-команда `import_test_server_music`;
* внешний HTTP-скрипт `scripts/import_test_server_music.py`.

Оба варианта используют один JSON-источник по умолчанию:

```
scripts/data/test_server_friendly_indie_payload.json
```

Структура JSON описана рядом:

```
scripts/data/test_server_content_payload.schema.json
```

Импорт идемпотентный: повторный запуск не требует очистки базы. Скрипты
переиспользуют уже созданных артистов, альбомы, треки и мерч по fixture-маркерам.
Обложки и картинки товаров генерируются скриптом, в JSON их указывать не нужно.

### Локальный импорт через Django

Команда работает внутри проекта через API-слой Django:

```
python manage.py import_test_server_music --disable-throttling
```

Указать другой JSON-источник:

```
python manage.py import_test_server_music \
  --payload scripts/data/test_server_friendly_indie_payload.json
```

Указать пароль для fixture-аккаунтов артистов:

```
python manage.py import_test_server_music \
  --password 'TestPass123!@#'
```

### Импорт через HTTP API
```
python -m scripts.import_test_server_music   --base-url https://myhost/api/v1
```

Этот вариант подходит для локального dev-сервера, staging или тестового сервера.
В `--base-url` указывается базовый адрес API v1.

Локальный сервер:

```
python scripts/import_test_server_music.py \
  --base-url http://127.0.0.1:8000/api/v1
```

Удаленный сервер:

```
python scripts/import_test_server_music.py \
  --base-url https://example.com/api/v1 \
  --payload scripts/data/test_server_friendly_indie_payload.json \
  --password 'TestPass123!@#'
```

Если сервер активно тротлит запросы, добавьте паузу после изменяющих запросов:

```
python scripts/import_test_server_music.py \
  --base-url https://example.com/api/v1 \
  --request-delay 0.5 \
  --timeout 30
```

Скрипт получает типы мерча из ручки `/store/merch-kinds/` и сопоставляет их
с каноническими типами `cassette`, `cap`, `cd`, `tshirt`, `vinyl`. Если подходящий
тип в базе не найден, товары этого типа пропускаются.

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
