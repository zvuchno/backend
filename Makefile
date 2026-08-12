.PHONY: help up up-d start start-d build down restart logs rebuild clean \
	shell migrations migrate test collectstatic

help:
	@echo "Доступные команды:"
	@echo "  make up            Собрать Docker image и запустить проект"
	@echo "  make up-d          Собрать Docker image и запустить в фоне"
	@echo "  make start         Запустить без пересборки"
	@echo "  make start-d       Запустить без пересборки в фоне"
	@echo "  make build         Собрать Docker images"
	@echo "  make rebuild       Пересобрать images без кэша и запустить в фоне"
	@echo "  make down          Остановить и удалить контейнеры"
	@echo "  make restart       Перезапустить контейнеры"
	@echo "  make logs          Показать логи"
	@echo "  make clean         Удалить контейнеры и неиспользуемый build-кэш"
	@echo "  make shell         Открыть Django shell"
	@echo "  make migrations    Создать миграции"
	@echo "  make migrate       Применить миграции"
	@echo "  make collectstatic Собрать статические файлы"
	@echo "  make test          Запустить тесты"

up-d: build
	docker compose up -d

up: build
	docker compose up

start:
	docker compose up

start-d:
	docker compose up -d

build:
	docker compose build

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

rebuild:
	docker compose build --no-cache
	docker compose up -d

clean:
	docker compose down --remove-orphans
	docker builder prune -f

shell:
	docker compose exec backend python manage.py shell

migrations:
	docker compose exec backend python manage.py makemigrations

migrate:
	docker compose exec backend python manage.py migrate

test:
	docker compose exec backend pytest

collectstatic:
	docker compose exec backend python manage.py collectstatic --noinput
