import stripe
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.user import UserResponse
from app.portal.models.plan import Plan
from app.portal.models.payment import Payment
from app.portal.plans import get_plan_by_id


async def get_or_create_stripe_customer(user: UserResponse, db: Session):
    """Get existing Stripe customer or create a new one."""
    try:
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
