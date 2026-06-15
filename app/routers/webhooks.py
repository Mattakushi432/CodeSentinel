import hashlib
import hmac
import json
import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.repository import Repository
from app.models.review_job import JobStatus, ReviewJob

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


class WebhookResponse(BaseModel):
    status: str
    job_id: int | None = None
    event: str | None = None
    action: str | None = None

# In-memory rate limiter: max 10 webhook requests per repo per 60 seconds
_RATE_LIMIT_MAX = 10
_RATE_LIMIT_WINDOW = 60
_rate_buckets: dict[int, list[float]] = defaultdict(list)


def _check_rate_limit(repo_id: int) -> bool:
    """Return True if allowed, False if rate limit exceeded."""
    now = time.monotonic()
    window_start = now - _RATE_LIMIT_WINDOW
    calls = _rate_buckets[repo_id]
    # Evict old entries
    _rate_buckets[repo_id] = [t for t in calls if t > window_start]
    if len(_rate_buckets[repo_id]) >= _RATE_LIMIT_MAX:
        return False
    _rate_buckets[repo_id].append(now)
    return True


def _verify_github_signature(payload: bytes, secret: str, signature_header: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _verify_gitlab_token(secret: str, token_header: str | None) -> bool:
    if not token_header:
        return False
    return hmac.compare_digest(secret, token_header)


def _verify_gitea_signature(payload: bytes, secret: str, signature_header: str | None) -> bool:
    return _verify_github_signature(payload, secret, signature_header)


@router.post("/{repo_id}", response_model=WebhookResponse)
async def receive_webhook(repo_id: int, request: Request, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.active == True).first()  # noqa: E712
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if not _check_rate_limit(repo_id):
        logger.warning("Rate limit exceeded for repo %d", repo_id)
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    payload_bytes = await request.body()
    secret = repo.webhook_secret

    if repo.git_host == "github":
        sig = request.headers.get("X-Hub-Signature-256")
        if not _verify_github_signature(payload_bytes, secret, sig):
            logger.warning("Invalid GitHub signature for repo %d", repo_id)
            raise HTTPException(status_code=401, detail="Invalid signature")

        event_type = request.headers.get("X-GitHub-Event", "")
        if event_type != "pull_request":
            return WebhookResponse(status="ignored", event=event_type)

        try:
            data = json.loads(payload_bytes)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        action = data.get("action", "")
        if action not in ("opened", "synchronize", "reopened"):
            return WebhookResponse(status="ignored", action=action)

        try:
            pr_number = int(data["pull_request"]["number"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid payload: missing or non-integer pr number")

    elif repo.git_host == "gitlab":
        token = request.headers.get("X-Gitlab-Token")
        if not _verify_gitlab_token(secret, token):
            raise HTTPException(status_code=401, detail="Invalid token")

        event_type = request.headers.get("X-Gitlab-Event", "")
        if "Merge Request" not in event_type:
            return WebhookResponse(status="ignored")

        try:
            data = json.loads(payload_bytes)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        action = data.get("object_attributes", {}).get("action", "")
        if action not in ("open", "update", "reopen"):
            return WebhookResponse(status="ignored", action=action)

        try:
            pr_number = int(data["object_attributes"]["iid"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid payload: missing or non-integer iid")

    elif repo.git_host == "gitea":
        sig = request.headers.get("X-Gitea-Signature")
        if not _verify_gitea_signature(payload_bytes, secret, f"sha256={sig}" if sig else None):
            raise HTTPException(status_code=401, detail="Invalid signature")

        try:
            data = json.loads(payload_bytes)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        action = data.get("action", "")
        if action not in ("opened", "synchronize", "reopened"):
            return WebhookResponse(status="ignored")

        try:
            pr_number = int(data["pull_request"]["number"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid payload: missing or non-integer pr number")

    else:
        raise HTTPException(status_code=400, detail="Unknown git host")

    existing = (
        db.query(ReviewJob)
        .filter(ReviewJob.repo_id == repo.id, ReviewJob.pr_number == pr_number, ReviewJob.status == JobStatus.pending)
        .first()
    )
    if existing:
        return WebhookResponse(status="already_queued", job_id=existing.id)

    job = ReviewJob(repo_id=repo.id, pr_number=pr_number, status=JobStatus.pending)
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info("Queued job %d for repo %d PR #%d", job.id, repo.id, pr_number)
    return WebhookResponse(status="queued", job_id=job.id)
