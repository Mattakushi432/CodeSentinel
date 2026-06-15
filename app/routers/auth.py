import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.organization import Organization
from app.models.user import User
from app.services.auth_service import generate_magic_token, verify_magic_token
from app.services.email_service import send_magic_link

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
async def login_submit(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    email = email.strip().lower()[:254]
    if not _EMAIL_RE.match(email):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Please enter a valid email address."},
        )
    settings = get_settings()
    token = generate_magic_token(email)
    magic_url = f"{settings.base_url}/auth/verify?token={token}"

    await send_magic_link(email, magic_url)
    return templates.TemplateResponse(
        "auth/magic_link_sent.html",
        {"request": request, "email": email},
    )


@router.get("/verify")
async def verify_magic_link(request: Request, token: str, db: Session = Depends(get_db)):
    email = verify_magic_token(token)
    if not email:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Link expired or invalid. Request a new one."},
        )

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


@router.get("/dev-login")
async def dev_login(request: Request, email: str = "zakr1995@gmail.com", db: Session = Depends(get_db)):
    """Dev-only shortcut — bypasses email sending."""
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
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=302, headers={"Location": "/auth/login"})
    return user
