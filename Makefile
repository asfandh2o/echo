.PHONY: help setup dev migrate-up migrate-down clean docker-up docker-down test

help:
	@echo "ECHO - AI Email Assistant"
	@echo "========================="
	@echo ""
	@echo "Available commands:"
	@echo "  make setup       - Initial setup (copy .env, install deps)"
	@echo "  make dev         - Start development server"
	@echo "  make worker      - Start Celery worker"
	@echo "  make beat        - Start Celery beat scheduler"
	@echo "  make migrate-up  - Run database migrations"
	@echo "  make migrate-down- Rollback last migration"
	@echo "  make docker-up   - Start all Docker services"
	@echo "  make docker-down - Stop all Docker services"
	@echo "  make clean       - Clean up cache and temp files"
	@echo "  make keys        - Generate security keys"

setup:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	pip install -r requirements.txt
	@echo "✅ Setup complete. Edit .env with your credentials."

dev:
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

worker:
	celery -A workers.celery_app worker --loglevel=info

beat:
	celery -A workers.celery_app beat --loglevel=info

migrate-up:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete

keys:
	python scripts/generate_keys.py
