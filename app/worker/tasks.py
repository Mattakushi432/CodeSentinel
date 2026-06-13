import asyncio
import logging

from app.config import get_settings
from app.database import SessionLocal
from app.models.review_job import JobStatus
from app.services.review_pipeline import run_review

logger = logging.getLogger(__name__)


async def review_worker() -> None:
    """SQLite-backed queue: poll for pending jobs, process one at a time."""
    settings = get_settings()
    logger.info("Review worker started (poll interval: %ds)", settings.worker_poll_interval)

    while True:
        try:
            with SessionLocal() as db:
                from app.models.review_job import ReviewJob
                job = (
                    db.query(ReviewJob)
                    .filter(ReviewJob.status == JobStatus.pending)
                    .order_by(ReviewJob.created_at.asc())
                    .first()
                )
                if job:
                    job_id = job.id
                    logger.info("Picked up job %d (PR #%d)", job_id, job.pr_number)
                else:
                    job_id = None

            if job_id is not None:
                with SessionLocal() as db:
                    await run_review(job_id, db)
            else:
                await asyncio.sleep(settings.worker_poll_interval)

        except asyncio.CancelledError:
            logger.info("Review worker shutting down")
            break
        except Exception as exc:
            logger.exception("Worker loop error: %s", exc)
            await asyncio.sleep(5)
