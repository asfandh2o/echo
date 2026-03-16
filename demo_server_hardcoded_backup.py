"""
ECHO Demo Server - Simplified version for local testing without PostgreSQL
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uvicorn

app = FastAPI(
    title="ECHO - AI Email Assistant (Demo)",
    description="Demo version without database dependencies",
    version="1.0.0-demo"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for demo
users_db = {}
emails_db = {}
suggestions_db = {}

# Pydantic models
class User(BaseModel):
    id: str
    email: str
    autonomy_level: str = "supervised"
    token_budget: int = 100000
    tokens_used_today: int = 0

class Email(BaseModel):
    id: str
    user_id: str
    subject: str
    sender: str
    body: str
    classification: Optional[dict] = None
    received_at: datetime

class Suggestion(BaseModel):
    id: str
    email_id: str
    suggestion_text: str
    confidence_score: float
    status: str = "pending"

@app.get("/")
async def root():
    return {
        "service": "ECHO Demo",
        "version": "1.0.0-demo",
        "status": "operational",
        "note": "This is a demo version. Full version requires Docker with PostgreSQL + Redis",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "demo_data": "/demo/populate"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "mode": "demo",
        "database": "in-memory",
        "features": [
            "API endpoints",
            "In-memory storage",
            "Mock classification",
            "Mock suggestions"
        ],
        "limitations": [
            "No persistent storage",
            "No Gmail integration",
            "No OpenAI integration",
            "No background workers"
        ]
    }

@app.post("/demo/populate")
async def populate_demo_data():
    """Populate with sample data for testing"""
    import uuid

    # Create demo user
    user_id = str(uuid.uuid4())
    users_db[user_id] = User(
        id=user_id,
        email="demo@example.com",
        autonomy_level="supervised",
        token_budget=100000,
        tokens_used_today=5000
    )

    # Create demo emails
    email_id_1 = str(uuid.uuid4())
    emails_db[email_id_1] = Email(
        id=email_id_1,
        user_id=user_id,
        subject="Project Update Request",
        sender="manager@company.com",
        body="Hi, can you send me an update on the Q1 project status?",
        classification={
            "urgent": False,
            "needs_response": True,
            "category": "work",
            "confidence": 0.92
        },
        received_at=datetime.now()
    )

    email_id_2 = str(uuid.uuid4())
    emails_db[email_id_2] = Email(
        id=email_id_2,
        user_id=user_id,
        subject="Urgent: Client Meeting Tomorrow",
        sender="client@external.com",
        body="We need to reschedule our meeting tomorrow. Can we move it to 3pm?",
        classification={
            "urgent": True,
            "needs_response": True,
            "category": "work",
            "confidence": 0.95
        },
        received_at=datetime.now()
    )

    # Create demo suggestions
    sugg_id_1 = str(uuid.uuid4())
    suggestions_db[sugg_id_1] = Suggestion(
        id=sugg_id_1,
        email_id=email_id_1,
        suggestion_text="Hi,\n\nThe Q1 project is progressing well. We're on track with our milestones and expect to deliver by the end of the month.\n\nBest regards",
        confidence_score=0.85,
        status="pending"
    )

    sugg_id_2 = str(uuid.uuid4())
    suggestions_db[sugg_id_2] = Suggestion(
        id=sugg_id_2,
        email_id=email_id_2,
        suggestion_text="Hi,\n\n3pm works perfectly for me. I'll update the calendar invite.\n\nThanks",
        confidence_score=0.92,
        status="pending"
    )

    return {
        "status": "success",
        "data": {
            "user_id": user_id,
            "emails_created": 2,
            "suggestions_created": 2
        },
        "access_endpoints": {
            "emails": f"/emails?user_id={user_id}",
            "suggestions": f"/suggestions?user_id={user_id}"
        }
    }

@app.get("/emails")
async def list_emails(user_id: str):
    """List emails for a user"""
    user_emails = [e for e in emails_db.values() if e.user_id == user_id]
    return {
        "count": len(user_emails),
        "emails": user_emails
    }

@app.get("/suggestions")
async def list_suggestions(user_id: str):
    """List suggestions for a user"""
    user_suggestions = []
    for sugg in suggestions_db.values():
        email = emails_db.get(sugg.email_id)
        if email and email.user_id == user_id:
            user_suggestions.append(sugg)

    return {
        "count": len(user_suggestions),
        "suggestions": user_suggestions
    }

@app.get("/suggestions/{suggestion_id}")
async def get_suggestion(suggestion_id: str):
    """Get a specific suggestion with email context"""
    suggestion = suggestions_db.get(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    email = emails_db.get(suggestion.email_id)

    return {
        "suggestion": suggestion,
        "email": email
    }

@app.post("/suggestions/{suggestion_id}/feedback")
async def submit_feedback(suggestion_id: str, feedback_type: str):
    """Submit feedback on a suggestion"""
    suggestion = suggestions_db.get(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    suggestion.status = "completed"

    return {
        "status": "success",
        "feedback_type": feedback_type,
        "message": f"Feedback '{feedback_type}' recorded for suggestion"
    }

@app.get("/architecture")
async def architecture_info():
    """Show the full architecture that this demo represents"""
    return {
        "demo_mode": True,
        "full_system_components": {
            "api_layer": "FastAPI (✓ Running in demo)",
            "database": "PostgreSQL + pgvector (✗ Requires Docker)",
            "cache": "Redis (✗ Requires Docker)",
            "background_workers": "Celery (✗ Requires Docker)",
            "llm_integration": "OpenAI GPT-4o (✗ Requires API key)",
            "oauth": "Google OAuth 2.0 (✗ Requires credentials)",
            "gmail_integration": "Gmail API (✗ Requires OAuth)",
            "calendar_integration": "Google Calendar API (✗ Requires OAuth)"
        },
        "to_run_full_system": {
            "1": "Install Docker Desktop",
            "2": "Add Google OAuth credentials to .env",
            "3": "Add OpenAI API key to .env",
            "4": "Run: docker-compose up -d",
            "5": "Run: docker-compose exec api alembic upgrade head",
            "6": "Access: http://localhost:8000"
        },
        "documentation": {
            "readme": "See README.md for full setup instructions",
            "architecture": "See ARCHITECTURE.md for system design",
            "quickstart": "See QUICKSTART.md for 5-minute setup guide"
        }
    }

if __name__ == "__main__":
    print("\n" + "="*60)
    print("ECHO Demo Server Starting")
    print("="*60)
    print("\nThis is a simplified demo version")
    print("Full version requires Docker + PostgreSQL + Redis\n")
    print("Access points:")
    print("  - API: http://localhost:8000")
    print("  - Docs: http://localhost:8000/docs")
    print("  - Health: http://localhost:8000/health")
    print("\nQuick start:")
    print("  1. Visit http://localhost:8000/docs")
    print("  2. POST /demo/populate to create sample data")
    print("  3. GET /emails?user_id=<id> to see emails")
    print("  4. GET /suggestions?user_id=<id> to see AI suggestions")
    print("\nFor full system:")
    print("  1. Install Docker Desktop")
    print("  2. Configure .env with OAuth + OpenAI credentials")
    print("  3. Run: docker-compose up -d")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
