# ECHO - Complete Project Structure

```
echo/
│
├── main.py                          # FastAPI application entry point
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variables template
├── .gitignore                       # Git ignore rules
├── Dockerfile                       # Container image definition
├── docker-compose.yml               # Multi-container orchestration
├── alembic.ini                      # Alembic configuration
├── Makefile                         # Development commands
├── README.md                        # Project documentation
├── ARCHITECTURE.md                  # Architecture deep-dive
│
├── core/                            # Core utilities and configuration
│   ├── __init__.py
│   ├── config.py                    # Settings management (Pydantic)
│   ├── security.py                  # Token encryption (Fernet/AES-256)
│   └── logging.py                   # Structured logging (structlog)
│
├── api/                             # FastAPI routes and dependencies
│   ├── __init__.py
│   ├── deps.py                      # Dependency injection (DB, auth)
│   └── routes/
│       ├── __init__.py
│       ├── auth.py                  # OAuth flow, JWT tokens
│       ├── emails.py                # Email CRUD endpoints
│       ├── suggestions.py           # Suggestion management
│       └── users.py                 # User management, export, delete
│
├── models/                          # SQLAlchemy ORM models
│   ├── __init__.py
│   ├── user.py                      # User accounts, OAuth tokens
│   ├── email.py                     # Email messages
│   ├── embedding.py                 # Vector embeddings (pgvector)
│   ├── suggestion.py                # AI suggestions
│   ├── style_profile.py             # Writing style profiles
│   └── feedback_log.py              # User feedback tracking
│
├── schemas/                         # Pydantic validation schemas
│   ├── __init__.py
│   ├── user.py                      # User DTOs
│   ├── email.py                     # Email DTOs
│   ├── suggestion.py                # Suggestion DTOs
│   └── style_profile.py             # Style profile DTOs
│
├── services/                        # Business logic layer
│   ├── __init__.py
│   ├── llm_router.py                # OpenAI integration, model selection
│   ├── gmail_service.py             # Gmail API integration
│   ├── classification_service.py    # Email classification
│   ├── suggestion_service.py        # Suggestion generation
│   ├── memory_service.py            # Embedding and similarity search
│   ├── style_service.py             # Style analysis and profiling
│   └── confidence_service.py        # Confidence scoring
│
├── tools/                           # External tool integrations
│   ├── __init__.py
│   ├── gmail_tool.py                # Safe Gmail operations
│   └── calendar_tool.py             # Google Calendar read-only
│
├── workers/                         # Celery background tasks
│   ├── __init__.py
│   ├── celery_app.py                # Celery configuration
│   └── tasks.py                     # Background task definitions
│
├── db/                              # Database session management
│   ├── __init__.py
│   └── session.py                   # Async SQLAlchemy session
│
├── migrations/                      # Alembic database migrations
│   ├── __init__.py
│   ├── env.py                       # Alembic environment
│   ├── script.py.mako               # Migration template
│   └── versions/
│       ├── __init__.py
│       └── 001_initial_schema.py    # Initial database schema
│
└── scripts/                         # Development utilities
    ├── dev_setup.sh                 # Development setup script
    └── generate_keys.py             # Security key generator
```

## File Count Summary

- **Core Modules**: 3 files
- **API Layer**: 5 files
- **Models**: 6 files
- **Schemas**: 4 files
- **Services**: 7 files
- **Tools**: 2 files
- **Workers**: 2 files
- **Database**: 1 file
- **Migrations**: 4 files
- **Configuration**: 7 files
- **Documentation**: 3 files
- **Scripts**: 2 files

**Total**: 46+ files

## Key Technologies

- **FastAPI** - Modern async web framework
- **SQLAlchemy 2.0** - Async ORM
- **PostgreSQL** - Primary database
- **pgvector** - Vector similarity search
- **Redis** - Cache and message broker
- **Celery** - Background task processing
- **Pydantic v2** - Data validation
- **OpenAI GPT-4o** - AI/LLM integration
- **Google OAuth 2.0** - Authentication
- **Alembic** - Database migrations
- **structlog** - Structured logging
- **Docker** - Containerization

## Database Tables

1. **users** - User accounts and OAuth tokens
2. **emails** - Ingested Gmail messages
3. **embeddings** - Vector embeddings for similarity search
4. **suggestions** - AI-generated email suggestions
5. **style_profiles** - User writing style analysis
6. **feedback_logs** - User feedback for training

## API Endpoints

### Auth
- `GET /auth/google/login` - Start OAuth flow
- `GET /auth/google/callback` - OAuth callback handler

### Emails
- `GET /emails/` - List user emails
- `GET /emails/{id}` - Get email detail
- `GET /emails/thread/{id}` - Get thread emails

### Suggestions
- `GET /suggestions/` - List pending suggestions
- `GET /suggestions/{id}` - Get suggestion detail
- `POST /suggestions/{id}/feedback` - Submit feedback

### Users
- `GET /users/me` - Get current user
- `PATCH /users/me` - Update user settings
- `GET /users/me/export` - Export all user data
- `DELETE /users/me` - Delete account and all data

### System
- `GET /` - Root endpoint
- `GET /health` - Health check

## Background Tasks

### Scheduled (Celery Beat)
- `fetch_emails_for_all_users` - Every 5 minutes
- `reset_daily_token_budgets` - Daily at midnight

### Event-Driven (Celery)
- `fetch_emails_for_user` - Per-user email fetch
- `classify_email` - Email classification
- `create_embedding` - Vector embedding generation
- `create_suggestion` - Suggestion generation
- `rebuild_style_profile` - Style profile update

## Running the System

### Quick Start (Docker)
```bash
docker-compose up -d
docker-compose exec api alembic upgrade head
```

### Development
```bash
make setup
make docker-up
make migrate-up
make dev        # Terminal 1
make worker     # Terminal 2
make beat       # Terminal 3
```

### Production
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Security Features

✅ AES-256 encrypted OAuth tokens at rest
✅ Multi-tenant data isolation (user_id scoping)
✅ JWT authentication for API access
✅ Safety verification for AI-generated content
✅ Audit logging for all tool actions
✅ GDPR-compliant data export and deletion
✅ Structured logging for security events
✅ No cross-tenant queries possible
✅ Cascade deletes for data cleanup

## Production Checklist

- [ ] Set strong `SECRET_KEY` (32+ chars)
- [ ] Set strong `ENCRYPTION_KEY` (Fernet key)
- [ ] Configure production `DATABASE_URL`
- [ ] Configure production `REDIS_URL`
- [ ] Set Google OAuth credentials (production)
- [ ] Set OpenAI API key (production)
- [ ] Enable HTTPS/TLS
- [ ] Configure CORS origins
- [ ] Set up monitoring (Sentry, CloudWatch, etc.)
- [ ] Configure log aggregation
- [ ] Set up automated backups
- [ ] Run database migrations
- [ ] Test OAuth flow end-to-end
- [ ] Test email ingestion
- [ ] Test suggestion generation
- [ ] Verify multi-tenancy isolation
- [ ] Load test API endpoints
- [ ] Set up health check monitoring
