import os
from typing import Optional
from app.models.plan import Plan

def get_plan_by_id(plan_id: str) -> Optional[Plan]:
    """Get a plan by its ID."""
    # This should ideally fetch from a database or a more dynamic config source.
    # For now, using the hardcoded dict:
    plans_config = {
        "basic": Plan(
            id="basic",
            name="Basic Plan",
            description="Perfect for individual users",
            price=9.99,
            duration_days=30,
            data_limit=100 * 1024 * 1024 * 1024,  # 100GB
            stripe_price_id=os.getenv("STRIPE_PRICE_ID_BASIC"),
            features=["1 Device", "100GB Data", "30 Days"]
        ),
        "premium": Plan(
            id="premium",
            name="Premium Plan",
            description="For power users and small families",
            price=19.99,
            duration_days=30,
            data_limit=500 * 1024 * 1024 * 1024,  # 500GB
            stripe_price_id=os.getenv("STRIPE_PRICE_ID_PREMIUM"),
            features=["3 Devices", "500GB Data", "30 Days"]
        ),
        "unlimited": Plan(
            id="unlimited",
            name="Unlimited Plan",
            description="Unlimited data for heavy users",
            price=29.99,
            duration_days=30,
            data_limit=None,  # None means unlimited
            stripe_price_id=os.getenv("STRIPE_PRICE_ID_UNLIMITED"),
            features=["5 Devices", "Unlimited Data", "30 Days"]
        )
    }
    return plans_config.get(plan_id)