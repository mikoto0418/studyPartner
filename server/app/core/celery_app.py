from datetime import timedelta

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
        "app.tasks.celery_tasks",
        "app.tasks.assessment_tasks",
    ],
    # Cron Beat Scheduler Configuration
    beat_schedule={
        "generate-daily-reviews-every-midnight": {
            "task": "app.tasks.celery_tasks.generate_daily_reviews_cron",
            "schedule": crontab(hour=0, minute=0),
        },
        "publish-scheduled-assessment-papers": {
            "task": "app.tasks.assessment_tasks.publish_scheduled_papers_task",
            "schedule": timedelta(minutes=1),
        },
        # 到点收卷：学生中断作答且不再回来时，attempt 会永远停在 in_progress
        "finalize-expired-assessment-attempts": {
            "task": "app.tasks.assessment_tasks.finalize_expired_attempts_task",
            "schedule": timedelta(minutes=5),
        },
    }
)
