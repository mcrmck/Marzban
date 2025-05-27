import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import uuid
from pydantic import BaseModel

from app.db import get_db
from app.models.user import UserResponse
from app.portal.models.plan import Plan
from app.portal.models.payment import Payment, PaymentStatus
from app.portal.auth import get_current_user
from config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET

router = APIRouter(prefix="/client-portal", tags=["Client Portal"])
templates = Jinja2Templates(directory="app/portal/templates")

stripe.api_key = STRIPE_SECRET_KEY


class CheckoutRequest(BaseModel):
    plan_id: str


def get_plan_by_id(plan_id: str) -> Plan:
    """Get a plan by its ID."""
    # TODO: Fetch from database
    plans = {
        "basic": Plan(
            id="basic",
            name="Basic Plan",
            description="Perfect for individual users",
            price=9.99,
            duration_days=30,
            data_limit=100 * 1024 * 1024 * 1024,  # 100GB
            stripe_price_id="price_basic",
            features=["1 Device", "100GB Data", "30 Days"]
        ),
        "premium": Plan(
            id="premium",
            name="Premium Plan",
            description="For power users and small families",
            price=19.99,
            duration_days=30,
            data_limit=500 * 1024 * 1024 * 1024,  # 500GB
            stripe_price_id="price_premium",
            features=["3 Devices", "500GB Data", "30 Days"]
        ),
        "unlimited": Plan(
            id="unlimited",
            name="Unlimited Plan",
            description="Unlimited data for heavy users",
            price=29.99,
            duration_days=30,
            data_limit=None,  # Unlimited
            stripe_price_id="price_unlimited",
            features=["5 Devices", "Unlimited Data", "30 Days"]
        )
    }
    return plans.get(plan_id)


@router.get("/", response_class=HTMLResponse)
async def portal_home(request: Request, db: Session = Depends(get_db)):
    """Render the portal home page with available plans."""
    # TODO: Fetch active plans from database
    plans = [
        get_plan_by_id("basic"),
        get_plan_by_id("premium"),
        get_plan_by_id("unlimited")
    ]

    return templates.TemplateResponse(
        "home.html",
        {"request": request, "plans": plans}
    )


@router.post("/create-checkout-session")
async def create_checkout_session(
    request: Request,
    checkout_request: CheckoutRequest,
    db: Session = Depends(get_db)
):
    """Create a Stripe checkout session for the selected plan."""
    plan = get_plan_by_id(checkout_request.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    try:
        # Create checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": plan.stripe_price_id,
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{request.base_url}client-portal/success"
            f"?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{request.base_url}client-portal/cancel",
            metadata={
                "plan_id": plan.id
            }
        )

        # Create payment record
        payment = Payment(
            id=str(uuid.uuid4()),
            plan_id=plan.id,
            amount=plan.price,
            stripe_payment_intent_id=session.payment_intent
        )
        db.add(payment)
        db.commit()

        return {"session_id": session.id, "url": session.url}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event.type == "checkout.session.completed":
        session = event.data.object
        payment = db.query(Payment).filter(
            Payment.stripe_payment_intent_id == session.payment_intent
        ).first()

        if payment:
            payment.status = PaymentStatus.COMPLETED
            # TODO: Activate user subscription
            db.commit()

    return Response(status_code=200)


@router.get("/success")
async def payment_success(
    request: Request,
    session_id: str,
    db: Session = Depends(get_db)
):
    """Handle successful payment."""
    return templates.TemplateResponse(
        "success.html",
        {"request": request, "session_id": session_id}
    )


@router.get("/cancel")
async def payment_cancel(request: Request):
    """Handle cancelled payment."""
    return templates.TemplateResponse(
        "cancel.html",
        {"request": request}
    )