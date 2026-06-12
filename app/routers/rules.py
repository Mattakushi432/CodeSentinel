from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.rule import Rule
from app.routers.auth import require_user

router = APIRouter(prefix="/rules", tags=["rules"])
templates = Jinja2Templates(directory="app/templates")


def _get_org(user: User, db: Session) -> Organization:
    org = db.query(Organization).filter(Organization.owner_id == user.id).first()
    if not org:
        raise HTTPException(status_code=404)
    return org


@router.get("", response_class=HTMLResponse)
async def list_rules(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _get_org(user, db)
    rules = db.query(Rule).filter(Rule.org_id == org.id).order_by(Rule.created_at.desc()).all()
    return templates.TemplateResponse("dashboard/rules.html", {"request": request, "user": user, "org": org, "rules": rules})


@router.post("")
async def add_rule(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    name: str = Form(...),
    description: str = Form(""),
    prompt_snippet: str = Form(""),
    language: str = Form("all"),
):
    org = _get_org(user, db)
    rule = Rule(
        org_id=org.id,
        name=name.strip(),
        description=description.strip() or None,
        prompt_snippet=prompt_snippet.strip() or None,
        language=language or "all",
    )
    db.add(rule)
    db.commit()
    return RedirectResponse(url="/rules", status_code=302)


@router.post("/{rule_id}/toggle")
async def toggle_rule(rule_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _get_org(user, db)
    rule = db.query(Rule).filter(Rule.id == rule_id, Rule.org_id == org.id).first()
    if rule:
        rule.enabled = not rule.enabled
        db.commit()
    return RedirectResponse(url="/rules", status_code=302)


@router.post("/{rule_id}/delete")
async def delete_rule(rule_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _get_org(user, db)
    rule = db.query(Rule).filter(Rule.id == rule_id, Rule.org_id == org.id).first()
    if rule:
        db.delete(rule)
        db.commit()
    return RedirectResponse(url="/rules", status_code=302)
