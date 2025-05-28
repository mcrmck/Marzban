from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import httpx
import os
from typing import Optional

from app.db import get_db
from app.portal.models.plan import Plan
from app.portal.auth import get_current_user, get_current_user_optional
from app.models.admin import Admin
from app.models.user import UserResponse

router = APIRouter(prefix="/client-portal", tags=["Client Portal"])
templates = Jinja2Templates(directory="app/portal/templates")


@router.get("/", response_class=HTMLResponse)
async def portal_home(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional) # Add dependency
):
    """Render the portal home page with available plans."""
    plans = [
        get_plan_by_id("basic"),
        get_plan_by_id("premium"),
        get_plan_by_id("unlimited")
    ]

    return templates.TemplateResponse(
        "home.html",
        # Pass current_user to the template
        {"request": request, "plans": plans, "current_user": current_user}
    )


@router.get("/servers", response_class=HTMLResponse)
async def servers_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional) # Add dependency
):
    """Render the servers page with available nodes/hosts."""
    api_url = os.getenv("API_URL", "https://localhost:8000")
    nodes_data = []

    try:
        # ... (Your existing httpx code to fetch nodes) ...
        pass # Keep your existing node fetching logic here

    except Exception as e:
        # ... (Your existing error handling) ...
        nodes_data = []

    return templates.TemplateResponse(
        "servers.html",
        # Pass current_user to the template
        {"request": request, "nodes": nodes_data, "current_user": current_user}
    )


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