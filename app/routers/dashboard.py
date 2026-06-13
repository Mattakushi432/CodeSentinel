from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.review_job import JobStatus, ReviewJob
from app.models.user import User
from app.routers.auth import require_user

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


def _get_user_org(user: User, db: Session) -> Organization | None:
    return db.query(Organization).filter(Organization.owner_id == user.id).first()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _get_user_org(user, db)
    if not org:
        return templates.TemplateResponse("dashboard/index.html", {"request": request, "user": user, "org": None})

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
        .filter(Repository.org_id == org.id)
        .order_by(ReviewJob.created_at.desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "repo_count": repo_count,
            "pending_count": pending_count,
            "total_reviews": total_reviews,
            "recent_jobs": recent_jobs,
        },
    )
