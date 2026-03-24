[![Main Zvuchno workflow](https://github.com/zvuchno/backend/actions/workflows/main.yml/badge.svg)](https://github.com/zvuchno/backend/actions/workflows/main.yml)
[![Website](https://img.shields.io/badge/Visit-Live%20Site-brightgreen)](https://zvuchno-dev.duckdns.org/)

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

Подготовьте окружение:
Создайте файл .env в корневой папке проекта на основе примера:
```
DEBUG=False
USE_SQLITE=False
POSTGRES_DB=zvuchno_db
POSTGRES_USER=admin
POSTGRES_PASSWORD=db%77&htc85
POSTGRES_HOST=db
POSTGRES_PORT=5432
```
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


# Продакшен / Деплой:
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

- Перейдите во вкладку Actions в репозитории
- В списке workflows выберите Main Zvuchno workflow
- Нажмите кнопку Run workflow

После этого GitHub запустит pipeline, который:
- соберёт Docker-образы
- отправит образы в Docker Hub
- выполнит деплой на сервер через SSH
