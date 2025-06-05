from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from .auth_utils import create_access_token
from app.db import get_db, crud
from app.models.user import UserCreate, UserStatusCreate, UserStatus, UserResponse # Make sure UserStatus is imported if used directly
from app import xray
from app.models.proxy import ProxyTypes
from app.portal.models.api import TokenResponse, ClientLoginRequest

import uuid
import os
from datetime import datetime # Import datetime

# Create two routers - one for HTML pages and one for API endpoints
api_router = APIRouter(prefix="/auth", tags=["Client Portal API"])


def readable_bytes_filter_auth(size_in_bytes):
    if size_in_bytes is None: return "Unlimited"
    if size_in_bytes == 0 and isinstance(size_in_bytes, int): return "0 B"
    if not isinstance(size_in_bytes, (int, float)) or size_in_bytes < 0:
         return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.1f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.1f} PB"

def timestamp_to_datetime_str_filter_auth(timestamp, format="%Y-%m-%d %H:%M"):
    if timestamp is None: return "N/A"
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime(format)
    except:
        return "Invalid Date"

def time_until_expiry_filter_auth(timestamp):
    if timestamp is None: return "Never"
    now = datetime.utcnow()
    expire_dt = datetime.fromtimestamp(int(timestamp))
    if now >= expire_dt:
        return "Expired"
    delta = expire_dt - now
    if delta.days > 0:
        return f"{delta.days} days left"
    elif delta.seconds // 3600 > 0:
        return f"{delta.seconds // 3600} hours left"
    elif delta.seconds // 60 > 0:
        return f"{delta.seconds // 60} minutes left"
    return "Soon"

# API Authentication Endpoints
@api_router.post("/token", response_model=TokenResponse)
async def api_login(
    login_data: ClientLoginRequest,
    db: Session = Depends(get_db)
):
    """API endpoint for client login. Returns a JWT token."""
    account_number = login_data.account_number.lower()
    user = crud.get_user(db, account_number=account_number)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid account number or account not found"
        )

    access_token = create_access_token(data={"sub": user.account_number})
    return TokenResponse(access_token=access_token, token_type="bearer")

@api_router.post("/register", response_model=TokenResponse)
async def api_register(
    db: Session = Depends(get_db)
):
    """API endpoint for client registration. Returns a JWT token."""
    generated_account_number = str(uuid.uuid4())

    default_proxies_for_new_user = {}
    try:
        if hasattr(xray, 'config') and hasattr(xray.config, 'inbounds_by_protocol'):
            for pt_enum_member in ProxyTypes:
                if xray.config.inbounds_by_protocol.get(pt_enum_member.value):
                    settings_model_class = pt_enum_member.settings_model
                    if settings_model_class:
                        default_proxies_for_new_user[pt_enum_member] = settings_model_class()
    except Exception as e:
        print(f"[DEBUG] Portal Reg: Error populating default proxies for {generated_account_number}: {str(e)}")

    try:
        user_payload = UserCreate(
            account_number=generated_account_number,
            proxies=default_proxies_for_new_user,
            status=UserStatusCreate.disabled,
            data_limit=None,
            expire=None,
            data_limit_reset_strategy="no_reset",
            note="Registered via Client Portal API",
            on_hold_expire_duration=None,
            on_hold_timeout=None,
            auto_delete_in_days=None,
            next_plan=None
        )
        new_db_user = crud.create_user(db=db, account_number=generated_account_number, user=user_payload, admin=None)
        access_token = create_access_token(data={"sub": new_db_user.account_number})
        return TokenResponse(access_token=access_token, token_type="bearer")

    except Exception as e:
        print(f"[DEBUG] Error during API registration for {generated_account_number}: {str(e)}")
        import traceback
        print(f"[DEBUG] Full traceback for {generated_account_number}:\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="Could not create account due to an internal error"
        )

@api_router.post("/logout")
async def api_logout(response: Response):
    """API endpoint for client logout. Clears the authentication cookie."""
    response = JSONResponse(content={"message": "Successfully logged out"})
    response.delete_cookie(key="access_token", path='/')
    return response

# Create the main router that includes both HTML and API routers
router = APIRouter()
router.include_router(api_router)