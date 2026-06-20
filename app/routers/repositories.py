import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.limiter import limiter
from app.models.organization import Organization
from app.models.repository import Repository
from app.models.user import User
from app.routers.auth import require_org, require_user
from app.templates_config import templates
from app.utils.ssrf import is_ssrf_url

router = APIRouter(prefix="/repos", tags=["repos"])

_REPO_NAME_RE = re.compile(r"^[\w.\-]+/[\w.\-]+$")
_URL_RE = re.compile(r"^https?://")


def _validate_repo_input(git_host: str, repo_full_name: str, base_url: str, access_token: str) -> str | None:
    """Return error string or None if valid."""
    if git_host not in ("github", "gitlab", "gitea"):
        return "Invalid git host"
    if not repo_full_name or len(repo_full_name) > 255:
        return "Repository name must be 1–255 characters"
    if not _REPO_NAME_RE.match(repo_full_name):
        return "Repository must be in owner/repo format (alphanumeric, dashes, dots)"
    if base_url:
        if len(base_url) > 500 or not _URL_RE.match(base_url):
            return "Base URL must start with http:// or https:// and be under 500 chars"
        if is_ssrf_url(base_url):
            return "Base URL must not point to a private or internal network address"
    if access_token and len(access_token) > 500:
        return "Access token too long (max 500 chars)"
    return None


@router.get("", response_class=HTMLResponse)
def list_repos(
    request: Request,
    user: User = Depends(require_user),
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    repos = db.query(Repository).filter(Repository.org_id == org.id).order_by(Repository.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "dashboard/repos.html",
        {"user": user, "org": org, "repos": repos, "base_url": settings.base_url},
    )


@router.post("")
@limiter.limit("20/minute")
def add_repo(
    request: Request,
    user: User = Depends(require_user),
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
    git_host: str = Form(...),
    repo_full_name: str = Form(...),
    base_url: str = Form(""),
    access_token: str = Form(""),
    settings: Settings = Depends(get_settings),
):

    repo_full_name = repo_full_name.strip()
    base_url = base_url.strip()
    access_token = access_token.strip()

    err = _validate_repo_input(git_host, repo_full_name, base_url, access_token)
    if err:
        repos = db.query(Repository).filter(Repository.org_id == org.id).all()
        return templates.TemplateResponse(
            request,
            "dashboard/repos.html",
            {"user": user, "org": org, "repos": repos, "base_url": settings.base_url, "error": err},
        )

    repo = Repository(
        org_id=org.id,
        git_host=git_host,
        repo_full_name=repo_full_name,
        base_url=base_url or None,
    )
    repo.set_access_token(access_token or None)
    db.add(repo)
    db.commit()
    return RedirectResponse(url="/repos", status_code=302)


@router.post("/{repo_id}/delete")
@limiter.limit("30/minute")
def delete_repo(
    request: Request,
    repo_id: int,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
):
    repo = db.query(Repository).filter(Repository.id == repo_id, Repository.org_id == org.id).first()
    if repo:
        repo.active = False
        db.commit()
    return RedirectResponse(url="/repos", status_code=302)
