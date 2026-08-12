.PHONY: \
	up up-d start start-d build \
	down restart logs rebuild clean \
	shell migrations migrate test

up-d: build
	docker compose up -d

up: build
	docker compose up

start:
	docker compose up

start-d:
	docker compose up -d

build:
	docker compose build backend

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

rebuild:
	docker compose build --no-cache backend
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
