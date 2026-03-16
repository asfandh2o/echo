# ECHO Architecture

## System Overview

ECHO is a production-grade, multi-tenant AI email assistant built with clean architecture principles.

## Layers

### 1. API Layer (`api/`)

**Responsibility**: HTTP interface, request validation, authentication

- `routes/auth.py` - Google OAuth flow, JWT token generation
- `routes/emails.py` - Email listing and retrieval
- `routes/suggestions.py` - Suggestion CRUD and feedback submission
- `routes/users.py` - User management, data export/deletion
- `deps.py` - Dependency injection (DB session, current user)

**Key Principles**:
- Routes are thin controllers
- No business logic in routes
- All I/O is async
- Pydantic validation on all inputs

### 2. Service Layer (`services/`)

**Responsibility**: Business logic, orchestration

- `gmail_service.py` - Gmail API integration
- `classification_service.py` - Email classification orchestration
- `suggestion_service.py` - Suggestion generation and feedback
- `memory_service.py` - Embedding creation and similarity search
- `style_service.py` - Writing style analysis
- `confidence_service.py` - Confidence scoring and risk assessment
- `llm_router.py` - LLM interaction, model selection, prompt engineering

**Key Principles**:
- Services own business logic
- Database session injected via constructor
- Services compose other services
- All operations are async

### 3. Model Layer (`models/`)

**Responsibility**: Database schema, ORM mappings

- `user.py` - User accounts, OAuth tokens
- `email.py` - Email messages
- `embedding.py` - Vector embeddings (pgvector)
- `suggestion.py` - AI-generated suggestions
- `style_profile.py` - User writing style
- `feedback_log.py` - User feedback for training

**Key Principles**:
- SQLAlchemy 2.0 declarative models
- All tables have UUID primary keys
- All data scoped by `user_id` (multi-tenancy)
- Proper indexes on foreign keys and query patterns
- Cascade deletes for data cleanup

### 4. Schema Layer (`schemas/`)

**Responsibility**: API contracts, validation

- Pydantic v2 models
- Request/response DTOs
- Input validation
- Type safety

### 5. Tools Layer (`tools/`)

**Responsibility**: External integrations, safe wrappers

- `gmail_tool.py` - Safe Gmail send with confirmation
- `calendar_tool.py` - Google Calendar read-only access

**Key Principles**:
- Tools wrap external APIs
- Audit logging for all actions
- Safety checks before mutations
- Confirmation required by default

### 6. Worker Layer (`workers/`)

**Responsibility**: Background task processing

- `celery_app.py` - Celery configuration, beat schedule
- `tasks.py` - Async background tasks

**Background Tasks**:
- Email ingestion (periodic)
- Email classification (event-driven)
- Embedding generation (event-driven)
- Suggestion creation (event-driven)
- Style profile updates (on-demand)
- Token budget reset (daily)

### 7. Core Layer (`core/`)

**Responsibility**: Cross-cutting concerns

- `config.py` - Environment-based configuration
- `security.py` - Token encryption (Fernet/AES-256)
- `logging.py` - Structured logging (structlog)

## Data Flow

### Email Ingestion Flow

```
Celery Beat (every 5 min)
  ↓
fetch_emails_for_all_users
  ↓
fetch_emails_for_user (per user)
  ↓
GmailService.fetch_recent_emails
  ↓
Save Email to DB
  ↓
Trigger: classify_email task
  ↓
Trigger: create_embedding task
```

### Classification Flow

```
classify_email task
  ↓
ClassificationService.classify_email
  ↓
LLMRouter.classify_email (GPT-4o-mini)
  ↓
Save classification to Email.classification
  ↓
If needs_response = true:
  ↓
Trigger: create_suggestion task
```

### Suggestion Creation Flow

```
create_suggestion task
  ↓
SuggestionService.create_suggestion
  ↓
Get thread context (last 5 emails)
  ↓
MemoryService.find_similar_emails (vector search)
  ↓
StyleService.get_style_profile
  ↓
LLMRouter.draft_reply (GPT-4o)
  ↓
LLMRouter.verify_reply (safety check)
  ↓
ConfidenceService.calculate_confidence
  ↓
Save Suggestion to DB
```

### Feedback Flow

```
User submits feedback (API)
  ↓
SuggestionService.submit_feedback
  ↓
Calculate diff_score
  ↓
Save FeedbackLog
  ↓
Update Suggestion status
  ↓
If accepted:
  ↓
GmailTool.send_email_safe
```

## Security Model

### Multi-Tenancy

- All queries filtered by `user_id`
- Row-level security via application logic
- No cross-tenant data leakage possible

### OAuth Token Storage

```python
# Storage
plaintext_tokens → JSON.dumps() → Fernet.encrypt() → DB

# Retrieval
DB → Fernet.decrypt() → JSON.loads() → credentials
```

### Authentication

- Google OAuth 2.0 for initial auth
- JWT tokens for API access
- `get_current_user` dependency extracts user from JWT
- All routes protected except `/auth/*`

### Data Deletion

- Cascade deletes configured at DB level
- `DELETE /users/me` removes all user data atomically

## LLM Routing Strategy

### Model Selection

| Task | Model | Why |
|------|-------|-----|
| Classification | gpt-4o-mini | Cost-effective, fast, structured output |
| Drafting | gpt-4o | High quality, nuanced understanding |
| Verification | gpt-4o-mini | Fast safety checks |
| Summarization | gpt-4o | Long context, high quality |

### Cost Control

- User-level token budgets (`token_budget` field)
- Daily reset (Celery beat task)
- Tracking via `tokens_used_today`
- Rate limiting possible at service layer

### Prompt Engineering

- Structured JSON outputs via `response_format`
- Explicit anti-hallucination instructions
- Context injection (thread, style, similar emails)
- Few-shot examples in style profile

## Scalability Considerations

### Database

- Connection pooling (20 base, 10 overflow)
- Async I/O throughout
- Proper indexes on all query patterns
- pgvector for efficient similarity search

### Background Tasks

- Celery for distributed task processing
- Task retries with exponential backoff
- Idempotent task design
- Task time limits (30 min hard, 25 min soft)

### Caching

- Redis backing Celery
- Can add caching layer for style profiles, embeddings
- LLM responses not cached (privacy)

### Horizontal Scaling

- Stateless API servers (scale via load balancer)
- Multiple Celery workers (scale via worker count)
- Shared PostgreSQL and Redis (managed services)

## Monitoring & Observability

### Structured Logging

```python
logger.info(
    "event_name",
    user_id=user_id,
    metric_name=value,
    extra_context=data
)
```

All logs are JSON-structured for easy parsing.

### Health Checks

- `GET /health` - Basic liveness probe
- Database connection check possible
- Redis connection check possible

### Metrics to Track

- Email ingestion rate
- Classification accuracy
- Suggestion acceptance rate
- Average confidence scores
- Token usage per user
- API response times
- Task queue depth

## Testing Strategy

### Unit Tests

- Test services in isolation
- Mock external dependencies (Gmail API, OpenAI)
- Pydantic validation tests

### Integration Tests

- Test API endpoints with test database
- Test Celery tasks with test broker
- Test OAuth flow with mock credentials

### End-to-End Tests

- Full flow from email ingestion to suggestion
- Feedback loop validation
- Multi-tenancy isolation verification

## Deployment

### Environment Variables

All configuration via environment variables (12-factor app).

### Database Migrations

- Alembic for schema versioning
- Forward and backward migrations
- Run `alembic upgrade head` on deploy

### Zero-Downtime Deploys

1. Deploy new API servers (blue-green)
2. Run migrations (backward compatible)
3. Restart Celery workers
4. Switch traffic to new API servers

## Future Enhancements

### Phase 4: Advanced Features

- Slack integration (full read/write)
- Notion integration (full read/write)
- Google Drive integration (read/write)
- Multi-inbox support (personal + work)
- Email templates and snippets
- Smart scheduling via Calendar
- Meeting prep automation

### Technical Improvements

- GraphQL API option
- WebSocket for real-time updates
- User-facing analytics dashboard
- A/B testing framework
- Fine-tuned classification model
- On-premise deployment option
