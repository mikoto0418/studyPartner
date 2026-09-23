from uuid import UUID

from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.assessment_service import AssessmentService

logger = get_task_logger(__name__)


@celery_app.task
def parse_assessment_paper_task(paper_id: str):
    logger.info(f"Starting assessment paper parsing: {paper_id}")

    async def process():
        async with SessionLocal() as db:
            await AssessmentService.run_parse(db, UUID(paper_id))

    try:
        from app.tasks.celery_tasks import run_async

        run_async(process())
        logger.info(f"Completed assessment paper parsing: {paper_id}")
    except Exception as e:
        logger.error(f"Failed to parse assessment paper {paper_id}: {e}", exc_info=True)


@celery_app.task
def publish_scheduled_papers_task():
    logger.info("Triggering scheduled assessment paper publishing")

    async def process():
        async with SessionLocal() as db:
            return await AssessmentService.publish_due_papers(db)

    try:
        from app.tasks.celery_tasks import run_async

        published = run_async(process())
        logger.info(f"Scheduled publishing finished: {published} paper(s) published")
    except Exception as e:
        logger.error(f"Failed to publish scheduled papers: {e}", exc_info=True)