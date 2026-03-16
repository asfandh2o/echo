# ECHO - Next Steps Guide

You've successfully set up ECHO with Groq AI! Here's your roadmap to full production.

## Current Status ✅

- ✅ Production-grade backend code (54 files)
- ✅ Groq AI integration (FREE)
- ✅ Groq demo running on port 8001
- ✅ Security keys generated
- ✅ Multi-provider LLM router (Groq/OpenAI)

## What You're Missing

- ❌ Docker (for PostgreSQL + Redis)
- ❌ Google OAuth credentials (for Gmail)
- ⚠️  Embedding service (Groq doesn't support embeddings)

---

## Path 1: Full Production System (Recommended)

### Step 1: Install Docker Desktop (Required)

**Download**: https://www.docker.com/products/docker-desktop

**Why**: Provides PostgreSQL, Redis, and isolates dependencies

**Install Time**: 5-10 minutes

### Step 2: Get Google OAuth Credentials

**Purpose**: Connect to Gmail to read/send emails

**Steps**:
1. Go to: https://console.cloud.google.com/
2. Create new project (or select existing)
3. Enable APIs:
   - Gmail API
   - Google Calendar API (optional)
   - Google Drive API (optional)
4. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8000/auth/google/callback`
5. Copy Client ID and Client Secret

**Add to `.env`**:
```bash
GOOGLE_CLIENT_ID=your-actual-client-id
GOOGLE_CLIENT_SECRET=your-actual-secret
```

### Step 3: Start Full System

```bash
# Navigate to project
cd C:\Users\Shaggy\echo

# Start all services
docker-compose up -d

# Run database migrations
docker-compose exec api alembic upgrade head

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
```

### Step 4: Test OAuth Flow

1. Visit: http://localhost:8000/auth/google/login
2. Complete Google OAuth
3. Get JWT token
4. Use token to access API

### Step 5: Trigger Email Ingestion

Once authenticated, emails will be:
- Fetched every 5 minutes automatically
- Classified with Groq AI
- Suggestions generated with Groq AI

**Or trigger manually**:
```bash
docker-compose exec worker celery -A workers.celery_app call workers.tasks.fetch_emails_for_user --args='["your-user-id"]'
```

---

## Path 2: Local Development (No Docker)

If you don't want Docker, you can run services locally:

### Requirements
- PostgreSQL 16 with pgvector extension
- Redis
- Python 3.11+

### Setup

**1. Install PostgreSQL**:
- Download: https://www.postgresql.org/download/
- Install pgvector extension
- Create database: `createdb echo`

**2. Install Redis**:
- Download: https://github.com/microsoftarchive/redis/releases
- Start: `redis-server`

**3. Update `.env`**:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/echo
REDIS_URL=redis://localhost:6379/0
```

**4. Install Python dependencies**:
```bash
cd C:\Users\Shaggy\echo
pip install -r requirements.txt
```

**5. Run migrations**:
```bash
alembic upgrade head
```

**6. Start services** (3 terminals):
```bash
# Terminal 1: API
uvicorn main:app --reload

# Terminal 2: Worker
celery -A workers.celery_app worker --loglevel=info

# Terminal 3: Beat scheduler
celery -A workers.celery_app beat --loglevel=info
```

---

## Path 3: Hybrid Approach (Recommended for Testing)

Use Docker for infrastructure, run Python locally for development:

```bash
# Start only DB and Redis
docker-compose up -d db redis

# Run migrations
alembic upgrade head

# Run API locally
uvicorn main:app --reload

# Run worker locally
celery -A workers.celery_app worker --loglevel=info
```

**Benefits**:
- Easy debugging
- Fast iteration
- Don't need to rebuild Docker images

---

## Solving the Embedding Problem

Groq doesn't support text embeddings (needed for similarity search).

### Option 1: Use OpenAI Just for Embeddings

Add to `.env`:
```bash
LLM_PROVIDER=groq  # Keep using Groq for classification/drafting
OPENAI_API_KEY=sk-your-key  # Use OpenAI only for embeddings
```

**Cost**: ~$0.0001 per embedding (very cheap)

### Option 2: Use Sentence Transformers (Local, Free)

```bash
pip install sentence-transformers
```

Update `services/llm_router.py` to use local embeddings:
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(text)
```

**Benefits**: Free, fast, no API needed

### Option 3: Use Cohere (Free Tier)

Sign up: https://cohere.com/
Add to `.env`:
```bash
COHERE_API_KEY=your-cohere-key
```

**Free tier**: 100 API calls/minute

---

## Feature Checklist

Track your progress:

### Infrastructure
- [ ] Docker Desktop installed
- [ ] PostgreSQL + pgvector running
- [ ] Redis running
- [ ] Migrations completed

### Authentication
- [ ] Google OAuth credentials obtained
- [ ] OAuth flow tested
- [ ] JWT token received

### Email Integration
- [ ] Gmail API enabled
- [ ] First email fetched
- [ ] Email classified by Groq
- [ ] Embedding created

### AI Suggestions
- [ ] First suggestion generated
- [ ] Suggestion reviewed
- [ ] Feedback submitted

### Production
- [ ] Style profile built (after 100+ sent emails)
- [ ] Confidence scoring working
- [ ] Background workers running
- [ ] User data export tested
- [ ] User data deletion tested

---

## Troubleshooting

### "Docker not found"
- Install Docker Desktop
- Restart terminal after install

### "PostgreSQL connection failed"
- Check Docker: `docker-compose ps`
- Check logs: `docker-compose logs db`
- Restart: `docker-compose restart db`

### "OAuth redirect mismatch"
- Google Console redirect URI must EXACTLY match:
  `http://localhost:8000/auth/google/callback`
- No trailing slash
- Correct port (8000 for production, 8001 for demo)

### "Groq rate limit exceeded"
- Free tier: 30 req/min
- Add delays between requests
- Or upgrade to paid tier

### "Embeddings not working"
- Groq doesn't support embeddings
- Choose Option 1, 2, or 3 above

---

## Performance Optimization

Once running, you can optimize:

### Database
- Add more indexes for common queries
- Increase connection pool size
- Enable query caching

### Redis
- Increase memory limit
- Enable persistence
- Add caching layers

### Celery
- Increase worker count: `--concurrency=4`
- Add task prioritization
- Enable result expiration

### Groq
- Batch requests when possible
- Use lighter models for classification
- Cache common classifications

---

## Monitoring

Track your system health:

### Logs
```bash
# API logs
docker-compose logs -f api

# Worker logs
docker-compose logs -f worker

# All logs
docker-compose logs -f
```

### Metrics to Watch
- Email fetch rate (target: every 5 min)
- Classification accuracy (monitor user feedback)
- Suggestion acceptance rate (goal: >70%)
- API response time (target: <500ms)
- Groq API usage (stay under free tier limits)

### Health Checks
```bash
# API health
curl http://localhost:8000/health

# Database connection
docker-compose exec api python -c "from db.session import engine; print('DB OK')"

# Redis connection
docker-compose exec redis redis-cli ping
```

---

## What's Next?

1. **Short term** (today):
   - Install Docker
   - Get Google OAuth credentials
   - Start full system

2. **Medium term** (this week):
   - Process first 100 emails
   - Generate first 50 suggestions
   - Build initial style profile

3. **Long term** (this month):
   - Reach 70%+ acceptance rate
   - Enable autonomous mode for high-confidence replies
   - Add Slack/Notion integrations

---

## Support

- **Documentation**: See README.md, ARCHITECTURE.md
- **Demo**: http://localhost:8001 (Groq-powered)
- **Full API**: http://localhost:8000 (when Docker running)

You're 80% there! Just need Docker + OAuth to go fully live. 🚀
