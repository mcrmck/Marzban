import stripe
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.user import UserResponse
from app.portal.models.plan import Plan
from app.portal.models.payment import Payment


async def get_or_create_stripe_customer(user: UserResponse, db: Session):
    """Get existing Stripe customer or create a new one."""
    try:
        # Check if user already has a Stripe customer ID
        existing_payment = db.query(Payment).filter(
            Payment.user_id == user.id,
            Payment.stripe_customer_id.isnot(None)
        ).first()

        if existing_payment and existing_payment.stripe_customer_id:
            return stripe.Customer.retrieve(existing_payment.stripe_customer_id)

        # Create new customer
        customer = stripe.Customer.create(
            email=user.email,
            name=user.username,
            metadata={"user_id": user.id}
        )
        return customer

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


def get_plan_by_id(plan_id: str) -> Plan:
    """Get plan by ID from database."""
    # TODO: Implement database query
    # For now, return mock data
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