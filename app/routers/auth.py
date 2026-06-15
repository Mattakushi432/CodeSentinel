import hashlib
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.limiter import limiter
from app.models.organization import Organization
from app.models.used_token import UsedToken
from app.models.user import User
from app.services.auth_service import generate_magic_token, verify_magic_token
from app.services.email_service import send_magic_link
from app.templates_config import templates

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
@limiter.limit("5/minute")
async def login_submit(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    email = email.strip().lower()[:254]
    if not _EMAIL_RE.match(email):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Please enter a valid email address."},
        )
    token = generate_magic_token(email)
    magic_url = f"{settings.base_url}/auth/verify?token={token}"

    await send_magic_link(email, magic_url)
    return templates.TemplateResponse(
        "auth/magic_link_sent.html",
        {"request": request, "email": email},
    )


@router.get("/verify")
def verify_magic_link(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    email = verify_magic_token(token)
    if not email:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Link expired or invalid. Request a new one."},
        )

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    if db.get(UsedToken, token_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Link already used. Request a new one."},
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, plan="free")
        db.add(user)
        db.flush()
        org = Organization(name=email.split("@")[0], owner_id=user.id, plan="free")
        db.add(org)

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.magic_link_expiry)
    db.add(UsedToken(token_hash=token_hash, expires_at=expires_at))
    db.commit()
    db.refresh(user)

    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


def dev_login(request: Request, email: str = "dev@localhost", db: Session = Depends(get_db)):
    """Dev-only shortcut — registered only when DEV_MODE=true in create_app()."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, plan="free")
        db.add(user)
        db.flush()
        org = Organization(name=email.split("@")[0], owner_id=user.id, plan="free")
        db.add(org)
        db.commit()
        db.refresh(user)
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


class _LoginRequired(Exception):
    """Raised by require_user when no authenticated session exists."""


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user:
        raise _LoginRequired()
    return user


def get_user_org(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Returns the user's Organization, or None if not yet created."""
    return db.query(Organization).filter(Organization.owner_id == user.id).first()


def require_org(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Returns the user's Organization or raises 404."""
    org = db.query(Organization).filter(Organization.owner_id == user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org
