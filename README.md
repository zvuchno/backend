# Звучно — Backend

Backend API проекта **Звучно**.


## Стек

* Python 3.12
* Django 5.2
* Django REST Framework
* django-allauth
* SimpleJWT
* SQLite (для локальной разработки)

Основные зависимости:

```
Django==5.2.12
djangorestframework==3.16.1
django-allauth==65.14.3
djangorestframework_simplejwt==5.5.1
django-filter==25.2
ruff==0.15.4
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