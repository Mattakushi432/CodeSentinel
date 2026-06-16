import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.models.organization import Organization
from app.models.user import User
from app.services.auth_service import hash_password, verify_password
from app.templates_config import templates

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_MIN_PASSWORD_LEN = 8


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
@limiter.limit("10/minute")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()[:254]
    if not _EMAIL_RE.match(email):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Please enter a valid email address."},
        )

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid email or password."},
        )

    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
@limiter.limit("5/minute")
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()[:254]

    if not _EMAIL_RE.match(email):
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Please enter a valid email address."},
        )
    if len(password) < _MIN_PASSWORD_LEN:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": f"Password must be at least {_MIN_PASSWORD_LEN} characters."},
        )
    if password != password_confirm:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Passwords do not match."},
        )

    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "An account with this email already exists."},
        )

    org = Organization(name=email.split("@")[0], owner_id=user.id)
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
    return db.query(Organization).filter(Organization.owner_id == user.id).first()


def require_org(user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.owner_id == user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org
