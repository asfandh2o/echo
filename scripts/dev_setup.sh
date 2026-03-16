#!/bin/bash

set -e

echo "🚀 ECHO Development Setup"
echo "=========================="

if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your credentials before continuing"
    exit 1
fi

echo "🐳 Starting Docker services..."
docker-compose up -d db redis

echo "⏳ Waiting for PostgreSQL..."
sleep 5

echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

echo "🗄️  Running database migrations..."
alembic upgrade head

echo "✅ Setup complete!"
echo ""
echo "To start the development server:"
echo "  uvicorn main:app --reload"
echo ""
echo "To start Celery worker:"
echo "  celery -A workers.celery_app worker --loglevel=info"
echo ""
echo "To start Celery beat:"
echo "  celery -A workers.celery_app beat --loglevel=info"
