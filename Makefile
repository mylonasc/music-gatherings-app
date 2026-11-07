.PHONY: backend-test backend-lint backend-typecheck frontend-install frontend-typecheck frontend-build compose-config compose-build up down

backend-test:
	python3 -m pytest backend/tests -q

backend-lint:
	python3 -m ruff check backend

backend-typecheck:
	python3 -m mypy backend/app

frontend-install:
	npm ci --prefix frontend

frontend-typecheck:
	npm run typecheck --prefix frontend

frontend-build:
	npm run build --prefix frontend

compose-config:
	docker compose config --quiet

compose-build:
	docker compose build

up:
	docker compose up --build

down:
	docker compose down
