import asyncio
import logging
from datetime import datetime, time, date, timedelta
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.user import User, Role, UserRole
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

async def run_daily_reviews_for_all_students(review_date: date):
    """Generates daily reviews for all active students in the system"""
    logger.info(f"Starting daily reviews generation for date: {review_date}")
    async with SessionLocal() as db:
        # Find all users with student role
        stmt = (
            select(User)
            .join(UserRole, User.id == UserRole.user_id)
            .join(Role, UserRole.role_id == Role.id)
            .where(Role.code == "student")
        )
        res = await db.execute(stmt)
        students = res.scalars().all()
        
        logger.info(f"Found {len(students)} students to generate daily reviews for.")
        for student in students:
            try:
                # Use a transaction block for each student to prevent one failure from blocking others
                await MemoryService.generate_daily_review(db, student.id, review_date)
            except Exception as e:
                logger.error(f"Failed to generate daily review for student {student.id}: {e}", exc_info=True)

async def scheduler_loop():
    """Background loop checking time and running task at 00:00 daily"""
    logger.info("Daily review scheduler loop started.")
    while True:
        try:
            now = datetime.now()
            # If hour and minute is 00:00, trigger for yesterday
            if now.hour == 0 and now.minute == 0:
                yesterday = (now - timedelta(days=1)).date()
                await run_daily_reviews_for_all_students(yesterday)
                # Sleep 65 seconds to avoid double triggering in the same minute
                await asyncio.sleep(65)
            else:
                # Sleep 30 seconds before checking again
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
            await asyncio.sleep(60)

_scheduler_task = None

def start_scheduler():
    global _scheduler_task
    if _scheduler_task is None:
        loop = asyncio.get_event_loop()
        _scheduler_task = loop.create_task(scheduler_loop())
        logger.info("Daily review scheduler successfully registered and started.")

def stop_scheduler():
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Daily review scheduler stopped.")
