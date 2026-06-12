from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.services.auth_service import generate_magic_token, verify_magic_token
from app.services.email_service import send_magic_link
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
async def login_submit(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    email = email.strip().lower()
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
