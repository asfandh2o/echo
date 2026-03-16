"""
ECHO Demo with REAL Groq AI - No Docker Required
Run this to test actual AI suggestions without full infrastructure
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uvicorn
import asyncio
import sys
sys.path.insert(0, '.')

from services.llm_router import MultiProviderLLMRouter

app = FastAPI(
    title="ECHO - AI Demo with Groq",
    description="Demo with REAL AI suggestions powered by Groq",
    version="1.0.0-groq"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
emails_db = {}
suggestions_db = {}

# Initialize Groq LLM Router
llm_router = MultiProviderLLMRouter()

class Email(BaseModel):
    id: str
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
    reasoning: str
    status: str = "pending"

@app.get("/")
async def root():
    return {
        "service": "ECHO Demo - Groq Powered",
        "version": "1.0.0-groq",
        "status": "operational",
        "ai_provider": llm_router.provider,
        "ai_model": llm_router.drafting_model,
        "note": "This demo uses REAL Groq AI for suggestions!",
        "endpoints": {
            "classify": "/classify",
            "draft": "/draft",
            "demo": "/demo/populate",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "mode": "groq-demo",
        "ai_provider": llm_router.provider,
        "model": llm_router.drafting_model,
        "features": [
            "REAL AI classification",
            "REAL AI drafting",
            "In-memory storage",
            "No database required"
        ]
    }

@app.post("/classify")
async def classify_email(subject: str, sender: str, body: str):
    """Classify an email using REAL Groq AI"""
    try:
        result = await llm_router.classify_email(
            email_content=body,
            subject=subject,
            sender=sender
        )

        return {
            "classification": result,
            "provider": llm_router.provider,
            "model": llm_router.classification_model
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/draft")
async def draft_reply(
    email_body: str,
    context: Optional[List[str]] = None,
    style_tone: str = "professional"
):
    """Draft a reply using REAL Groq AI"""
    try:
        result = await llm_router.draft_reply(
            email_content=email_body,
            thread_context=context or [],
            similar_emails=[],
            style_profile={
                "tone": style_tone,
                "formality": "neutral",
                "avg_length": 100
            }
        )

        return {
            "draft": result.get("draft"),
            "confidence": result.get("confidence"),
            "reasoning": result.get("reasoning"),
            "provider": llm_router.provider,
            "model": llm_router.drafting_model
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/demo/populate")
async def populate_with_ai():
    """Create demo data and generate REAL AI suggestions"""
    import uuid

    user_id = str(uuid.uuid4())

    # Create demo emails
    demo_emails = [
        {
            "subject": "Project Update Request",
            "sender": "manager@company.com",
            "body": "Hi, can you send me an update on the Q1 project status? I need it for the board meeting tomorrow."
        },
        {
            "subject": "Urgent: Client Meeting",
            "sender": "client@external.com",
            "body": "We need to reschedule our meeting tomorrow. Can we move it to 3pm? Let me know ASAP."
        },
        {
            "subject": "Question about Invoice",
            "sender": "accounting@company.com",
            "body": "I noticed invoice #12345 hasn't been processed yet. Could you check on this when you get a chance?"
        }
    ]

    created_emails = []
    created_suggestions = []

    for demo in demo_emails:
        email_id = str(uuid.uuid4())

        # REAL AI Classification
        classification = await llm_router.classify_email(
            email_content=demo["body"],
            subject=demo["subject"],
            sender=demo["sender"]
        )

        email = Email(
            id=email_id,
            subject=demo["subject"],
            sender=demo["sender"],
            body=demo["body"],
            classification=classification,
            received_at=datetime.now()
        )
        emails_db[email_id] = email
        created_emails.append(email)

        # Generate REAL AI Suggestion
        if classification.get("needs_response"):
            draft = await llm_router.draft_reply(
                email_content=demo["body"],
                thread_context=[],
                similar_emails=[],
                style_profile={
                    "tone": "professional",
                    "formality": "neutral"
                }
            )

            sugg_id = str(uuid.uuid4())
            suggestion = Suggestion(
                id=sugg_id,
                email_id=email_id,
                suggestion_text=draft.get("draft", ""),
                confidence_score=draft.get("confidence", 0.0),
                reasoning=draft.get("reasoning", ""),
                status="pending"
            )
            suggestions_db[sugg_id] = suggestion
            created_suggestions.append(suggestion)

    return {
        "status": "success",
        "ai_provider": llm_router.provider,
        "ai_model": llm_router.drafting_model,
        "emails_created": len(created_emails),
        "suggestions_created": len(created_suggestions),
        "note": "All suggestions generated by REAL Groq AI!",
        "emails": [
            {
                "id": e.id,
                "subject": e.subject,
                "classification": e.classification
            }
            for e in created_emails
        ],
        "suggestions": [
            {
                "id": s.id,
                "email_id": s.email_id,
                "confidence": s.confidence_score,
                "preview": s.suggestion_text[:100] + "..."
            }
            for s in created_suggestions
        ]
    }

@app.get("/emails")
async def list_emails():
    return {
        "count": len(emails_db),
        "emails": list(emails_db.values())
    }

@app.get("/suggestions")
async def list_suggestions():
    return {
        "count": len(suggestions_db),
        "suggestions": list(suggestions_db.values()),
        "ai_provider": llm_router.provider,
        "note": "These are REAL AI-generated suggestions!"
    }

@app.get("/suggestions/{suggestion_id}")
async def get_suggestion(suggestion_id: str):
    suggestion = suggestions_db.get(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    email = emails_db.get(suggestion.email_id)

    return {
        "suggestion": suggestion,
        "email": email,
        "ai_provider": llm_router.provider,
        "ai_model": llm_router.drafting_model
    }

if __name__ == "__main__":
    print("\n" + "="*60)
    print("ECHO Demo with REAL Groq AI")
    print("="*60)
    print(f"\nAI Provider: {llm_router.provider}")
    print(f"Model: {llm_router.drafting_model}")
    print("\nThis demo uses REAL AI - not hardcoded responses!\n")
    print("Access points:")
    print("  - API: http://localhost:8001")
    print("  - Docs: http://localhost:8001/docs")
    print("\nQuick start:")
    print("  1. Visit http://localhost:8001/docs")
    print("  2. POST /demo/populate to generate AI suggestions")
    print("  3. GET /suggestions to see REAL AI drafts")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8001)
