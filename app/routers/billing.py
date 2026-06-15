import asyncio
import functools
import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.organization import Organization
from app.models.user import User
from app.routers.auth import require_user

router = APIRouter(prefix="/billing", tags=["billing"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

PLAN_PRICES = {"pro": "stripe_price_pro", "team": "stripe_price_team"}


async def _stripe_run(fn, **kwargs):
    """Run a blocking Stripe SDK call in a thread pool."""
    stripe.api_key = get_settings().stripe_secret_key
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(fn, **kwargs))


@router.get("", response_class=HTMLResponse)
def billing_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.owner_id == user.id).first()
    return templates.TemplateResponse(
        "dashboard/billing.html",
        {"request": request, "user": user, "org": org},
    )


@router.post("/checkout/{plan}")
async def create_checkout(plan: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Billing not configured")

    price_attr = PLAN_PRICES.get(plan)
    if not price_attr:
        raise HTTPException(status_code=400, detail="Invalid plan")

    price_id = getattr(settings, price_attr, "")
    if not price_id:
        raise HTTPException(status_code=503, detail="Plan price not configured")

    org = db.query(Organization).filter(Organization.owner_id == user.id).first()

    customer_id = user.stripe_customer_id
    if not customer_id:
        customer = await _stripe_run(stripe.Customer.create, email=user.email)
        user.stripe_customer_id = customer.id
        db.commit()
        customer_id = customer.id

    session = await _stripe_run(
        stripe.checkout.Session.create,
        customer=customer_id,
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.base_url}/billing?success=1",
        cancel_url=f"{settings.base_url}/billing",
        metadata={"org_id": str(org.id), "plan": plan},
    )
    return RedirectResponse(url=session.url, status_code=303)


@router.post("/stripe-webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook not configured")

    stripe.api_key = settings.stripe_secret_key
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except (stripe.SignatureVerificationError, ValueError) as e:
        logger.warning("Stripe webhook validation failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    if event["type"] == "checkout.session.completed":
        session_data = event["data"]["object"]
        org_id = int(session_data["metadata"]["org_id"])
        plan = session_data["metadata"]["plan"]
        sub_id = session_data["subscription"]

        org = db.get(Organization, org_id)
        if org:
            org.plan = plan
            org.stripe_subscription_id = sub_id
            db.commit()
            logger.info("Org %d upgraded to %s", org_id, plan)

    elif event["type"] == "customer.subscription.deleted":
        sub_id = event["data"]["object"]["id"]
        org = db.query(Organization).filter(Organization.stripe_subscription_id == sub_id).first()
        if org:
            org.plan = "free"
            org.stripe_subscription_id = None
            db.commit()
            logger.info("Org %d downgraded to free (subscription cancelled)", org.id)

    return JSONResponse({"status": "ok"})


@router.post("/portal")
async def customer_portal(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Redirect to Stripe Customer Portal for subscription management."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Billing not configured")

    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No active subscription")

    portal = await _stripe_run(
        stripe.billing_portal.Session.create,
        customer=user.stripe_customer_id,
        return_url=f"{settings.base_url}/billing",
    )
    return RedirectResponse(url=portal.url, status_code=303)
