# ECHO - Quick Start Guide

Get ECHO running in under 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- Google Cloud Project with OAuth 2.0 credentials
- OpenAI API key

## Step 1: Get OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable APIs:
   - Gmail API
   - Google Calendar API
   - Google Drive API
4. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8000/auth/google/callback`
5. Copy Client ID and Client Secret

## Step 2: Get OpenAI API Key

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Navigate to API Keys
3. Create new secret key
4. Copy the key (starts with `sk-`)

## Step 3: Configure Environment

```bash
cd echo
cp .env.example .env
```

Edit `.env`:

```bash
# Google OAuth (REQUIRED)
GOOGLE_CLIENT_ID=your-client-id-here
GOOGLE_CLIENT_SECRET=your-client-secret-here
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# OpenAI (REQUIRED)
OPENAI_API_KEY=sk-your-key-here

# Security Keys (REQUIRED - generate with: python scripts/generate_keys.py)
SECRET_KEY=your-64-char-hex-string
ENCRYPTION_KEY=your-fernet-key-base64
```

Generate security keys:

```bash
python scripts/generate_keys.py
```

Copy the output to your `.env` file.

## Step 4: Start Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- API server (port 8000)
- Celery worker
- Celery beat scheduler

## Step 5: Run Database Migration

```bash
docker-compose exec api alembic upgrade head
```

## Step 6: Test the System

### Check Health

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"healthy"}`

### Visit API Docs

Open browser: http://localhost:8000/docs

### Start OAuth Flow

```bash
curl http://localhost:8000/auth/google/login
```

Copy the `authorization_url` and open in browser.

Complete the OAuth flow.

You'll get back a JWT token:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "...",
    "email": "your@email.com"
  }
}
```

### Test Authenticated Request

```bash
export TOKEN="your-jwt-token-here"

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/users/me
```

## Step 7: Watch the Logs

### API Logs
```bash
docker-compose logs -f api
```

### Worker Logs
```bash
docker-compose logs -f worker
```

### Beat Scheduler Logs
```bash
docker-compose logs -f beat
```

## Expected Behavior

After OAuth flow completes:

1. **Immediate**: User account created in database
2. **Within 5 minutes**: First email fetch runs (Celery beat)
3. **Automatically**: Emails classified, embeddings created, suggestions generated

## Monitoring Progress

### List Your Emails

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/emails/
```

### List Suggestions

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/suggestions/
```

### Get a Suggestion

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/suggestions/{suggestion-id}
```

### Submit Feedback (Accept)

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"feedback_type": "accepted"}' \
  http://localhost:8000/suggestions/{suggestion-id}/feedback
```

### Submit Feedback (Edit)

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "feedback_type": "edited",
    "final_text": "Your edited version of the email"
  }' \
  http://localhost:8000/suggestions/{suggestion-id}/feedback
```

## Common Issues

### "Could not connect to database"

Database container not ready. Wait 10 seconds and retry.

```bash
docker-compose ps
```

Ensure `db` status is "Up".

### "Invalid OAuth credentials"

Check your `.env`:
- `GOOGLE_CLIENT_ID` matches your Google Cloud Console
- `GOOGLE_CLIENT_SECRET` matches your Google Cloud Console
- `GOOGLE_REDIRECT_URI` is exactly `http://localhost:8000/auth/google/callback`

### "Could not validate credentials" (JWT)

Token expired or invalid. Re-authenticate via OAuth flow.

### "No emails fetched"

Check Celery beat is running:

```bash
docker-compose logs beat
```

Should see:
```
Scheduler: Sending due task fetch-emails-all-users
```

Manually trigger:

```bash
docker-compose exec worker celery -A workers.celery_app call workers.tasks.fetch_emails_for_user --args='["your-user-id"]'
```

### Worker not processing tasks

Restart worker:

```bash
docker-compose restart worker
```

Check worker logs:

```bash
docker-compose logs worker
```

## Development Mode

For faster iteration without Docker:

### Start PostgreSQL and Redis

```bash
docker-compose up -d db redis
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Migrations

```bash
alembic upgrade head
```

### Start API (Terminal 1)

```bash
uvicorn main:app --reload
```

### Start Worker (Terminal 2)

```bash
celery -A workers.celery_app worker --loglevel=info
```

### Start Beat (Terminal 3)

```bash
celery -A workers.celery_app beat --loglevel=info
```

## Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- Read [README.md](README.md) for full documentation
- Explore the API at http://localhost:8000/docs
- Monitor logs to watch the system learn your email patterns
- Adjust confidence thresholds in `.env`
- Build a frontend UI

## Getting Help

- Check logs: `docker-compose logs -f`
- Check database: `docker-compose exec db psql -U postgres -d echo`
- Check Redis: `docker-compose exec redis redis-cli`
- API docs: http://localhost:8000/docs

## Stopping the System

```bash
docker-compose down
```

Preserve data:

```bash
docker-compose down
```

Remove all data:

```bash
docker-compose down -v
```
