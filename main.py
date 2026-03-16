from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from core.logging import configure_logging, get_logger
from api.routes import auth, emails, suggestions, users, calendar, digests, chat, notifications, tasks, metrics, documents
from db.session import engine, Base

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="ECHO - AI Email Assistant",
    description="Production-grade autonomous email assistant with Gmail integration",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(emails.router)
app.include_router(suggestions.router)
app.include_router(users.router)
app.include_router(calendar.router)
app.include_router(digests.router)
app.include_router(chat.router)
app.include_router(notifications.router)
app.include_router(tasks.router)
app.include_router(metrics.router)
app.include_router(documents.router)


@app.on_event("startup")
async def startup_event():
    logger.info("application_starting", environment=settings.ENVIRONMENT)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("application_shutting_down")
    await engine.dispose()


@app.get("/")
async def root():
    return {
        "service": "ECHO",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development"
    )
