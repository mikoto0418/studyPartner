import asyncio
from uuid import UUID
from datetime import date, timedelta
from celery.utils.log import get_task_logger
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.knowledge_service import KnowledgeService
from app.services.memory_service import MemoryService

logger = get_task_logger(__name__)

# Secure Event loop helper for Celery workers
def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@celery_app.task
def parse_document_task(doc_id: str):
    logger.info(f"Starting Celery async document processing: {doc_id}")
    
    async def process():
        async with SessionLocal() as db:
            await KnowledgeService.process_document(db, UUID(doc_id))
            
    try:
        run_async(process())
        logger.info(f"Completed Celery document processing: {doc_id}")
    except Exception as e:
        logger.error(f"Failed to process document {doc_id} in Celery: {e}", exc_info=True)

@celery_app.task
def generate_daily_reviews_cron():
    logger.info("Triggering Celery CRON: generate daily reviews for all active student users")
    
    async def process():
        from sqlalchemy import select
        from app.models.user import User, Role
        async with SessionLocal() as db:
            # Find all users with student role
            stmt = select(User).join(User.roles).where(Role.code == "student")
            res = await db.execute(stmt)
            students = res.scalars().all()
            
            logger.info(f"Found {len(students)} students to process.")
            
            # Yesterday date
            yesterday_val = date.today() - timedelta(days=1)
            
            for st in students:
                try:
                    logger.info(f"Generating review for student: {st.username} for date: {yesterday_val}")
                    # Trigger the review and memory extraction
                    await MemoryService.generate_daily_review(db, st.id, yesterday_val)
                    # We commit after each student to persist progress
                    await db.commit()
                except Exception as ex:
                    logger.error(f"Failed to generate review for student {st.username}: {ex}", exc_info=True)
                    await db.rollback()
                    
    try:
        run_async(process())
        logger.info("Cron daily reviews generation finished.")
    except Exception as e:
        logger.error(f"Failed to complete daily reviews cron job: {e}", exc_info=True)

@celery_app.task
def generate_single_student_review_task(student_id: str, date_str: str):
    logger.info(f"Starting single student daily review generation for {student_id} on {date_str}")
    async def process():
        async with SessionLocal() as db:
            d_val = date.fromisoformat(date_str)
            await MemoryService.generate_daily_review(db, UUID(student_id), d_val)
            await db.commit()
    try:
        run_async(process())
        logger.info(f"Successfully generated review for student {student_id} on {date_str}")
    except Exception as e:
        logger.error(f"Failed to generate review in Celery: {e}", exc_info=True)
