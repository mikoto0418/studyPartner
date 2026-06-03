from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "study_partner_tasks",
    broker=settings.redis_url,
    backend=settings.redis_url
)

# Configuration settings for Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    # List of tasks modules to load
    imports=[
        "app.tasks.celery_tasks"
    ],
    # Cron Beat Scheduler Configuration
    beat_schedule={
        "generate-daily-reviews-every-midnight": {
            "task": "app.tasks.celery_tasks.generate_daily_reviews_cron",
            "schedule": crontab(hour=0, minute=0),
        }
    }
)
