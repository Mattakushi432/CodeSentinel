import asyncio
import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.database import SessionLocal
from app.models.review_job import JobStatus
from app.services.review_pipeline import run_review

logger = logging.getLogger(__name__)

async def review_worker() -> None:
    """SQLite-backed queue: poll for pending jobs, process one at a time."""
    settings = get_settings()
    logger.info("Review worker started (poll interval: %ds)", settings.worker_poll_interval)

    if not settings.encryption_key:
        logger.warning(
            "ENCRYPTION_KEY is not set — access tokens are stored as plaintext. "
            "Set ENCRYPTION_KEY to a Fernet key to enable at-rest encryption."
        )

    while True:
        job_id = None
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
                    await run_review(job_id, db)
                else:
                    await asyncio.sleep(settings.worker_poll_interval)

        except asyncio.CancelledError:
            logger.info("Review worker shutting down")
            break
        except Exception as exc:
            logger.exception("Worker loop error: %s", exc)
            if job_id is not None:
                try:
                    with SessionLocal() as recovery_db:
                        from app.models.review_job import ReviewJob
                        stuck = recovery_db.get(ReviewJob, job_id)
                        if stuck and stuck.status == JobStatus.processing:
                            stuck.status = JobStatus.error
                            stuck.error_msg = "Worker error — see server logs"
                            stuck.finished_at = datetime.now(timezone.utc)
                            recovery_db.commit()
                except Exception as recovery_exc:
                    logger.error("Failed to mark job %d as error: %s", job_id, recovery_exc)
            await asyncio.sleep(5)
