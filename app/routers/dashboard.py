from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.review_job import JobStatus, ReviewJob
from app.models.user import User
from app.routers.auth import get_user_org, require_user
from app.templates_config import templates

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: User = Depends(require_user),
    org: Organization | None = Depends(get_user_org),
    db: Session = Depends(get_db),
):
    if not org:
        return templates.TemplateResponse(request, "dashboard/index.html", {"user": user, "org": None})

    repo_count = db.query(Repository).filter(Repository.org_id == org.id, Repository.active == True).count()  # noqa: E712
    pending_count = (
        db.query(ReviewJob)
        .join(Repository)
        .filter(Repository.org_id == org.id, ReviewJob.status == JobStatus.pending)
        .count()
    )
    total_reviews = (
        db.query(ReviewJob)
        .join(Repository)
        .filter(Repository.org_id == org.id, ReviewJob.status == JobStatus.done)
        .count()
    )
    recent_jobs = (
        db.query(ReviewJob)
        .join(Repository)
        .options(joinedload(ReviewJob.repository), joinedload(ReviewJob.review))
        .filter(Repository.org_id == org.id)
        .order_by(ReviewJob.created_at.desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        {
            "user": user,
            "org": org,
            "repo_count": repo_count,
            "pending_count": pending_count,
            "total_reviews": total_reviews,
            "recent_jobs": recent_jobs,
        },
    )
