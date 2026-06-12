from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.review_job import ReviewJob
from app.routers.auth import require_user

router = APIRouter(prefix="/reviews", tags=["reviews"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def list_reviews(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    repo_id: int | None = Query(None),
):
    org = db.query(Organization).filter(Organization.owner_id == user.id).first()
    if not org:
        return templates.TemplateResponse("dashboard/reviews.html", {"request": request, "user": user, "jobs": [], "org": None})

    repos = db.query(Repository).filter(Repository.org_id == org.id).all()
    query = db.query(ReviewJob).join(Repository).filter(Repository.org_id == org.id)

    if repo_id:
        query = query.filter(ReviewJob.repo_id == repo_id)

    per_page = 20
    total = query.count()
    jobs = query.order_by(ReviewJob.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    return templates.TemplateResponse(
        "dashboard/reviews.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "jobs": jobs,
            "repos": repos,
            "selected_repo_id": repo_id,
            "page": page,
            "total": total,
            "per_page": per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
        },
    )


@router.get("/job/{job_id}/status", response_class=HTMLResponse)
async def job_status(
    job_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """HTMX polling endpoint for live job status updates."""
    org = db.query(Organization).filter(Organization.owner_id == user.id).first()
    job = db.query(ReviewJob).join(Repository).filter(ReviewJob.id == job_id, Repository.org_id == org.id).first()
    return templates.TemplateResponse("partials/job_row.html", {"request": request, "job": job})
