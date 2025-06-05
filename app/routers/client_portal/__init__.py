from fastapi import APIRouter


# Import and include client portal specific routers
from . import (
    account,
    auth,
    subscription,
)
from fastapi import Depends, Request
from sqlalchemy.orm import Session
from app.db import get_db, crud
from app.portal.models.api import TokenResponse, ClientLoginRequest


router = APIRouter()

# Include all client portal routers
router.include_router(auth.router)
router.include_router(account.router)
router.include_router(subscription.router)


@router.post("/register", response_model=TokenResponse)
async def register_direct_route(db: Session = Depends(get_db)):
    """Direct register route that proxies to auth.register"""
    from .auth import api_register
    return await api_register(db=db)

@router.post("/login", response_model=TokenResponse)
async def login_direct_route(login_data: ClientLoginRequest, db: Session = Depends(get_db)):
    """Direct login route that proxies to auth.token"""
    from .auth import api_login
    return await api_login(login_data=login_data, db=db)

@router.post("/logout")
async def logout_direct_route():
    """Direct logout route that proxies to auth.logout"""
    from .auth import api_logout
    from fastapi import Response
    response = Response()
    return await api_logout(response=response)

@router.get("/account/plans")
async def plans_direct_route(db: Session = Depends(get_db)):
    """Direct plans route - get all available plans"""
    from app.db.models import Plan
    try:
        plans = db.query(Plan).all()
        # Convert to list of dicts for JSON response
        plan_list = []
        for plan in plans:
            plan_dict = {
                "id": plan.id,
                "name": plan.name,
                "description": plan.description,
                "price": plan.price,
                "duration_days": plan.duration_days,
                "data_limit": plan.data_limit,
                "stripe_price_id": plan.stripe_price_id,
                "features": plan.features or []
            }
            plan_list.append(plan_dict)
        return plan_list
    except Exception as e:
        print(f"Error fetching plans: {e}")
        # For now, return empty list if no plans table exists
        return []

@router.get("/servers")
async def servers_direct_route(
    request: Request,
    db: Session = Depends(get_db)
):
    """Direct servers route that proxies to account.servers"""
    from .account import get_servers
    from .auth_utils import get_current_user
    from app.db.models import User as DBUser

    # Get current user and convert to DB user object
    current_user = await get_current_user(request, db)
    current_user_orm: DBUser = crud.get_user(db, account_number=current_user.account_number)

    return await get_servers(request=request, db=db, current_user_orm=current_user_orm)

__all__ = ["router"]