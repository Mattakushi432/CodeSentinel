from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.organization import Organization
from app.models.rule import Rule
from app.models.user import User
from app.routers.auth import require_org, require_user

router = APIRouter(prefix="/rules", tags=["rules"])
templates = Jinja2Templates(directory="app/templates")

_ALLOWED_LANGUAGES = {"all", "python", "javascript", "go", "rust", "java", "typescript", "ruby", "php", "csharp"}


@router.get("", response_class=HTMLResponse)
async def list_rules(
    request: Request,
    user: User = Depends(require_user),
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
):
    rules = db.query(Rule).filter(Rule.org_id == org.id).order_by(Rule.created_at.desc()).all()
    return templates.TemplateResponse("dashboard/rules.html", {"request": request, "user": user, "org": org, "rules": rules})


@router.post("")
async def add_rule(
    request: Request,
    user: User = Depends(require_user),
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
    name: str = Form(...),
    description: str = Form(""),
    prompt_snippet: str = Form(""),
    language: str = Form("all"),
):
    name = name.strip()[:100]
    if not name:
        raise HTTPException(status_code=400, detail="Rule name is required")
    description = description.strip()[:500]
    prompt_snippet = prompt_snippet.strip()[:2000]
    language = language if language in _ALLOWED_LANGUAGES else "all"

    rule = Rule(
        org_id=org.id,
        name=name,
        description=description or None,
        prompt_snippet=prompt_snippet or None,
        language=language,
    )
    db.add(rule)
    db.commit()
    return RedirectResponse(url="/rules", status_code=302)


@router.post("/{rule_id}/toggle")
async def toggle_rule(
    rule_id: int,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
):
    rule = db.query(Rule).filter(Rule.id == rule_id, Rule.org_id == org.id).first()
    if rule:
        rule.enabled = not rule.enabled
        db.commit()
    return RedirectResponse(url="/rules", status_code=302)


@router.post("/{rule_id}/delete")
async def delete_rule(
    rule_id: int,
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
):
    rule = db.query(Rule).filter(Rule.id == rule_id, Rule.org_id == org.id).first()
    if rule:
        db.delete(rule)
        db.commit()
    return RedirectResponse(url="/rules", status_code=302)
