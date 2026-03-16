from celery import Celery
from celery.schedules import crontab
from core.config import settings

celery_app = Celery(
    "echo",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["workers.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
)

celery_app.conf.beat_schedule = {
    "fetch-emails-all-users": {
        "task": "workers.tasks.fetch_emails_for_all_users",
        "schedule": crontab(minute=f"*/{settings.EMAIL_FETCH_INTERVAL_MINUTES}"),
    },
    "reset-daily-token-budgets": {
        "task": "workers.tasks.reset_daily_token_budgets",
        "schedule": crontab(hour=0, minute=0),
    },
    "generate-daily-digests": {
        "task": "workers.tasks.generate_digests_for_all_users",
        "schedule": crontab(hour=6, minute=0),
    },
    "check-deadline-reminders": {
        "task": "workers.tasks.check_deadline_reminders",
        "schedule": crontab(minute="*/30"),
    },
    "scan-drive-all-users": {
        "task": "workers.tasks.scan_drive_for_all_users",
        "schedule": crontab(minute=0, hour=f"*/{settings.DRIVE_SCAN_INTERVAL_HOURS}"),
    },
}

if __name__ == "__main__":
    celery_app.start()
