from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.models.organization import Organization
from app.models.user import User
from app.routers.auth import require_org, require_user
from app.services.llm import PROVIDER_REGISTRY
from app.templates_config import templates

router = APIRouter(prefix="/settings", tags=["settings"])

_VALID_PROVIDERS = set(PROVIDER_REGISTRY.keys())


@router.get("/llm", response_class=HTMLResponse)
def llm_settings_page(
    request: Request,
    user: User = Depends(require_user),
    org: Organization = Depends(require_org),
):
    current_provider = org.llm_provider_override or ""
    current_model = org.llm_model_override or ""
    has_key = bool(org.llm_api_key_enc)
    return templates.TemplateResponse(
        request,
        "dashboard/settings_llm.html",
        {
            "user": user,
            "org": org,
            "providers": PROVIDER_REGISTRY,
            "current_provider": current_provider,
            "current_model": current_model,
            "has_key": has_key,
        },
    )


@router.post("/llm")
@limiter.limit("20/minute")
def save_llm_settings(
    request: Request,
    user: User = Depends(require_user),
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
    provider: str = Form(""),
    model: str = Form(""),
    api_key: str = Form(""),
):
    provider = provider.strip()
    model = model.strip()[:100]
    api_key = api_key.strip()

    if provider and provider not in _VALID_PROVIDERS:
        return templates.TemplateResponse(
            request,
            "dashboard/settings_llm.html",
            {
                "user": user,
                "org": org,
                "providers": PROVIDER_REGISTRY,
                "current_provider": provider,
                "current_model": model,
                "has_key": bool(org.llm_api_key_enc),
                "error": "Unknown provider selected.",
            },
        )

    org.llm_provider_override = provider or None
    org.llm_model_override = model or None
    if api_key:
        org.set_llm_api_key(api_key)
    elif not provider:
        org.set_llm_api_key(None)

    db.commit()
    return RedirectResponse(url="/settings/llm?saved=1", status_code=302)


@router.post("/llm/clear")
@limiter.limit("20/minute")
def clear_llm_settings(
    request: Request,
    user: User = Depends(require_user),
    org: Organization = Depends(require_org),
    db: Session = Depends(get_db),
):
    org.llm_provider_override = None
    org.llm_model_override = None
    org.set_llm_api_key(None)
    db.commit()
    return RedirectResponse(url="/settings/llm", status_code=302)
