# ECHO - AI Email Assistant

Production-grade autonomous email assistant with Gmail integration, powered by OpenAI GPT-4o.

## Architecture

- **FastAPI** - Async REST API
- **PostgreSQL** with **pgvector** - Multi-tenant database with vector similarity search
- **Redis** + **Celery** - Background task processing
- **SQLAlchemy 2.0** - Async ORM
- **OpenAI GPT-4o** - LLM routing and email understanding
- **Google OAuth 2.0** - Secure Gmail/Calendar integration

## Features

### Phase 1: Observation
- Gmail inbox monitoring
- Email classification (urgent, needs response, category)
- Learning from user behavior
- Style profile building from sent emails

### Phase 2: Supervised Suggestions
- AI-powered reply drafting
- User feedback loop (accept/edit/reject)
- Context-aware suggestions using thread history and similar emails

### Phase 3: Autonomous Execution
- Confidence-based automation
- High-confidence replies auto-send (optional)
- Safety verification for all drafts

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Google Cloud Project with OAuth 2.0 credentials
- OpenAI API key

### 1. Clone and Setup

```bash
cd echo
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` with your credentials:

```bash
# Google OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# OpenAI
OPENAI_API_KEY=sk-your-key

# Security (generate secure keys)
SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

### 3. Start Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL with pgvector
- Redis
- FastAPI application (port 8000)
- Celery worker
- Celery beat scheduler

### 4. Run Migrations

```bash
docker-compose exec api alembic upgrade head
```

### 5. Access API

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Manual Setup (Without Docker)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start PostgreSQL and Redis

```bash
# PostgreSQL with pgvector
docker run -d --name echo-db -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=echo \
  pgvector/pgvector:pg16

# Redis
docker run -d --name echo-redis -p 6379:6379 redis:7-alpine
```

### 3. Run Migrations

```bash
alembic upgrade head
```

### 4. Start API Server

```bash
uvicorn main:app --reload
```

### 5. Start Celery Worker

```bash
celery -A workers.celery_app worker --loglevel=info
```

### 6. Start Celery Beat

```bash
celery -A workers.celery_app beat --loglevel=info
```

## API Usage

### 1. Authenticate with Google

```bash
GET /auth/google/login
```

Returns authorization URL. User completes OAuth flow.

### 2. OAuth Callback

```bash
GET /auth/google/callback?code=<code>
```

Returns JWT token.

### 3. List Emails

```bash
GET /emails/
Authorization: Bearer <token>
```

### 4. Get Suggestions

```bash
GET /suggestions/
Authorization: Bearer <token>
```

### 5. Submit Feedback

```bash
POST /suggestions/{id}/feedback
Authorization: Bearer <token>

{
  "feedback_type": "accepted",
  "final_text": "optional edited text"
}
```

### 6. Export User Data

```bash
GET /users/me/export
Authorization: Bearer <token>
```

### 7. Delete Account

```bash
DELETE /users/me
Authorization: Bearer <token>
```

## Background Tasks

Celery handles:

- **Email Fetching**: Every 5 minutes (configurable)
- **Email Classification**: On new email
- **Embedding Generation**: For similarity search
- **Suggestion Creation**: For emails needing response
- **Style Profile Updates**: On demand
- **Token Budget Reset**: Daily at midnight

## Security

- OAuth tokens encrypted at rest (AES-256 via Fernet)
- Multi-tenant data isolation (all queries scoped by user_id)
- JWT authentication for API access
- Safety verification for all AI-generated content
- Audit logging for all tool actions
- GDPR-compliant data export and deletion

## Configuration

Key settings in `.env`:

```bash
# LLM Models
CLASSIFICATION_MODEL=gpt-4o-mini     # Cost-effective classification
DRAFTING_MODEL=gpt-4o                # High-quality drafting
SUMMARIZATION_MODEL=gpt-4o

# Confidence Thresholds
AUTO_SEND_THRESHOLD=0.95             # Auto-send only at very high confidence
APPROVAL_THRESHOLD=0.70              # Show for approval
SUGGESTION_THRESHOLD=0.50            # Show as suggestion

# Processing
EMAIL_FETCH_INTERVAL_MINUTES=5
MAX_EMAILS_PER_FETCH=50
STYLE_PROFILE_SAMPLE_SIZE=200
```

## Database Schema

- `users` - User accounts and OAuth tokens
- `emails` - Ingested Gmail messages
- `embeddings` - Vector embeddings for similarity search
- `suggestions` - AI-generated reply drafts
- `style_profiles` - User writing style analysis
- `feedback_logs` - User feedback for ML improvement

## Production Deployment

### Recommended Stack

- **Hosting**: AWS ECS / Google Cloud Run / Railway
- **Database**: Managed PostgreSQL with pgvector support
- **Redis**: Managed Redis (ElastiCache / Cloud Memorystore)
- **Monitoring**: Sentry + CloudWatch / Stackdriver

### Environment Variables

Ensure all production secrets are set:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/echo
REDIS_URL=redis://host:6379/0
SECRET_KEY=<strong-random-key>
ENCRYPTION_KEY=<fernet-key>
GOOGLE_CLIENT_ID=<production-client-id>
GOOGLE_CLIENT_SECRET=<production-secret>
OPENAI_API_KEY=<production-key>
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### Health Checks

```bash
GET /health
```

Returns `{"status": "healthy"}` when operational.

## Development

### Code Structure

```
echo/
├── core/           # Configuration, security, logging
├── api/            # FastAPI routes
├── models/         # SQLAlchemy models
├── schemas/        # Pydantic schemas
├── services/       # Business logic
├── tools/          # External integrations (Gmail, Calendar)
├── workers/        # Celery tasks
├── db/             # Database session management
└── migrations/     # Alembic migrations
```

### Adding a New Model

1. Create model in `models/`
2. Import in `models/__init__.py`
3. Create migration: `alembic revision --autogenerate -m "description"`
4. Apply: `alembic upgrade head`

### Adding a New Service

1. Create service in `services/`
2. Inject `AsyncSession` via constructor
3. Use in routes via dependency injection

## License

Proprietary
