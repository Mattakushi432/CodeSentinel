from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.review_job import ReviewJob
from app.models.user import User
from app.routers.auth import get_user_org, require_org, require_user
from app.templates_config import templates

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("", response_class=HTMLResponse)
def list_reviews(
    request: Request,
    user: User = Depends(require_user),
    org: Organization | None = Depends(get_user_org),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    repo_id: int | None = Query(None),
):
    if not org:
        return templates.TemplateResponse("dashboard/reviews.html", {"request": request, "user": user, "jobs": [], "org": None})

    repos = db.query(Repository).filter(Repository.org_id == org.id).all()
    query = db.query(ReviewJob).join(Repository).filter(Repository.org_id == org.id)

    if repo_id:
        query = query.filter(ReviewJob.repo_id == repo_id)

    per_page = 20
    total = query.count()
    jobs = (
        query.options(joinedload(ReviewJob.repository), joinedload(ReviewJob.review))
        .order_by(ReviewJob.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    total_pages = max(1, (total + per_page - 1) // per_page)
    page_range = range(max(1, page - 3), min(total_pages + 1, page + 4))
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
            "total_pages": total_pages,
            "page_range": page_range,
        },
    )


@router.get("/job/{job_id}/status", response_class=HTMLResponse)
def job_status(
    job_id: int,
    request: Request,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
):
    """HTMX polling endpoint for live job status updates."""
    job = (
        db.query(ReviewJob)
        .join(Repository)
        .options(joinedload(ReviewJob.repository), joinedload(ReviewJob.review))
        .filter(ReviewJob.id == job_id, Repository.org_id == org.id)
        .first()
    )
    return templates.TemplateResponse("partials/job_row.html", {"request": request, "job": job})


@router.get("/{job_id}", response_class=HTMLResponse)
def review_detail(
    job_id: int,
    request: Request,
    user: User = Depends(require_user),
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
):
    """Detailed view of a single review job with all issues."""
    job = (
        db.query(ReviewJob)
        .join(Repository)
        .options(joinedload(ReviewJob.repository), joinedload(ReviewJob.review))
        .filter(ReviewJob.id == job_id, Repository.org_id == org.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Review not found")
    return templates.TemplateResponse(
        "dashboard/review_detail.html",
        {"request": request, "user": user, "org": org, "job": job},
    )
