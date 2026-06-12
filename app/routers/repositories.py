from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.repository import Repository
from app.routers.auth import require_user
from app.config import get_settings

router = APIRouter(prefix="/repos", tags=["repos"])
templates = Jinja2Templates(directory="app/templates")


def _get_org(user: User, db: Session) -> Organization:
    org = db.query(Organization).filter(Organization.owner_id == user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.get("", response_class=HTMLResponse)
async def list_repos(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _get_org(user, db)
    repos = db.query(Repository).filter(Repository.org_id == org.id).order_by(Repository.created_at.desc()).all()
    settings = get_settings()
    return templates.TemplateResponse(
        "dashboard/repos.html",
        {"request": request, "user": user, "org": org, "repos": repos, "base_url": settings.base_url},
    )


@router.post("")
async def add_repo(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    git_host: str = Form(...),
    repo_full_name: str = Form(...),
    base_url: str = Form(""),
    access_token: str = Form(""),
):
    org = _get_org(user, db)
    active_count = db.query(Repository).filter(Repository.org_id == org.id, Repository.active == True).count()  # noqa: E712
    if active_count >= org.repo_limit:
        repos = db.query(Repository).filter(Repository.org_id == org.id).all()
        settings = get_settings()
        return templates.TemplateResponse(
            "dashboard/repos.html",
            {
                "request": request,
                "user": user,
                "org": org,
                "repos": repos,
                "base_url": settings.base_url,
                "error": f"Plan limit reached ({org.repo_limit} repos). Upgrade to add more.",
            },
        )

    repo = Repository(
        org_id=org.id,
        git_host=git_host,
        repo_full_name=repo_full_name.strip(),
        base_url=base_url.strip() or None,
        access_token=access_token.strip() or None,
    )
    db.add(repo)
    db.commit()
    return RedirectResponse(url="/repos", status_code=302)


@router.post("/{repo_id}/delete")
async def delete_repo(
    repo_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    org = _get_org(user, db)
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.org_id == org.id).first()
    if repo:
        repo.active = False
        db.commit()
    return RedirectResponse(url="/repos", status_code=302)
