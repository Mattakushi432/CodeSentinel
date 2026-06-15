import asyncio
import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.database import SessionLocal
from app.models.review_job import JobStatus
from app.services.review_pipeline import run_review

logger = logging.getLogger(__name__)

_CLEANUP_INTERVAL = 3600  # prune expired UsedToken rows once per hour
_cleanup_counter = 0


def _prune_expired_tokens(db) -> None:
    from app.models.used_token import UsedToken
    deleted = db.query(UsedToken).filter(UsedToken.expires_at < datetime.now(timezone.utc)).delete()
    db.commit()
    if deleted:
        logger.info("Pruned %d expired used_tokens", deleted)


async def review_worker() -> None:
    """SQLite-backed queue: poll for pending jobs, process one at a time."""
    global _cleanup_counter
    settings = get_settings()
    logger.info("Review worker started (poll interval: %ds)", settings.worker_poll_interval)

    if not settings.encryption_key:
        logger.warning(
            "ENCRYPTION_KEY is not set — access tokens are stored as plaintext. "
            "Set ENCRYPTION_KEY to a Fernet key to enable at-rest encryption."
        )

    while True:
        try:
            job_id = None
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
                    job.status = JobStatus.processing  # atomic claim before releasing the session
                    db.commit()
                    logger.info("Picked up job %d (PR #%d)", job_id, job.pr_number)

                _cleanup_counter += 1
                if _cleanup_counter * settings.worker_poll_interval >= _CLEANUP_INTERVAL:
                    _cleanup_counter = 0
                    _prune_expired_tokens(db)

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
