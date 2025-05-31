from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.portal.auth import create_access_token
from app.db import get_db, crud
from app.models.user import UserCreate, UserStatusCreate, UserStatus # Make sure UserStatus is imported if used directly
from app import xray
from app.models.proxy import ProxyTypes

import uuid
import os
from datetime import datetime # Import datetime

router = APIRouter(prefix="/client-portal", tags=["Client Portal Auth"])
templates = Jinja2Templates(directory="app/portal/templates")
templates.env.globals['datetime'] = datetime # Make datetime available in templates
templates.env.globals['UserStatus'] = UserStatus # Also ensure UserStatus enum is available if compared in templates

# ... (rest of your auth.py code)
# Make sure placeholder filters from previous response are also handled here if base.html is rendered from auth routes directly
# For example, if login_page or register_page directly render base.html without extending.
# However, they extend base.html, so filters defined in main.py's template instance should be available if main.py is the primary entry.
# To be safe, if these routes render templates that extend base.html, the globals should be consistent.
# The Jinja filters like readable_bytes were added to main.py's templates instance.
# If auth.py renders a page that itself extends base.html, it will use its own 'templates' instance.
# Thus, globals and filters should ideally be defined centrally or on each instance.

# For simplicity, adding the same filters here too, assuming they might be needed.
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

templates.env.filters["readable_bytes"] = readable_bytes_filter_auth
templates.env.filters["timestamp_to_datetime_str"] = timestamp_to_datetime_str_filter_auth
templates.env.filters["time_until_expiry"] = time_until_expiry_filter_auth
templates.env.globals["os"] = os


@router.get("/login", response_class=HTMLResponse, name="portal_login_page")
async def login_page(request: Request):
    """Render the login page."""
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )

@router.get("/register", response_class=HTMLResponse, name="portal_register_page")
async def register_page(request: Request):
    """Render the registration page."""
    return templates.TemplateResponse(
        "register.html",
        {"request": request}
    )

@router.post("/token", name="login") # For url_for('login') in login.html form
async def login_for_access_token(
    request: Request,
    db: Session = Depends(get_db)
):
    form_data = await request.form()
    account_number = form_data.get("account_number")

    if not account_number:
        # Pass error to template for display
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Account Number is required."},
            status_code=400
        )

    account_number = account_number.lower()
    user = crud.get_user(db, account_number=account_number)

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid Account Number or account not found."},
            status_code=400
        )

    access_token = create_access_token(data={"sub": user.account_number})

    redirect_url = request.url_for("portal_account_page")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        path='/', # Changed from '/client-portal' to '/'
        samesite='lax',
        secure=request.url.scheme == "https",
        max_age=1800
    )
    return response

@router.post("/register", name="register")
async def register_user(
    request: Request,
    db: Session = Depends(get_db)
):
    print("[DEBUG] Starting user registration process")
    generated_account_number = str(uuid.uuid4())
    print(f"[DEBUG] Generated account number: {generated_account_number}")

    # --- BEGIN MODIFICATION ---
    # Populate default proxies for the new portal user
    default_proxies_for_new_user = {}
    try:
        if hasattr(xray, 'config') and hasattr(xray.config, 'inbounds_by_protocol'):
            for pt_enum_member in ProxyTypes:
                if xray.config.inbounds_by_protocol.get(pt_enum_member.value):
                    settings_model_class = pt_enum_member.settings_model
                    if settings_model_class:
                        print(f"[DEBUG] Portal Reg: Adding default proxy for {pt_enum_member.value} to {generated_account_number}")
                        default_proxies_for_new_user[pt_enum_member] = settings_model_class()
                    else:
                        print(f"[DEBUG] Portal Reg: Protocol '{pt_enum_member.value}' has no settings_model for {generated_account_number}.")
                else:
                    print(f"[DEBUG] Portal Reg: Protocol '{pt_enum_member.value}' not in xray.config or no inbounds for {generated_account_number}.")
        else:
            print("[DEBUG] Portal Reg: xray.config or xray.config.inbounds_by_protocol not available for populating default proxies.")
    except Exception as e:
        print(f"[DEBUG] Portal Reg: Error populating default proxies for {generated_account_number}: {str(e)}")
    # --- END MODIFICATION ---

    try:
        print("[DEBUG] Creating UserCreate payload")
        user_payload = UserCreate(
            account_number=generated_account_number,
            proxies=default_proxies_for_new_user, # Use the populated defaults
            status=UserStatusCreate.disabled, # Users start disabled, plan activation changes this
            data_limit=None,
            expire=None,
            data_limit_reset_strategy="no_reset", # Consider making this configurable
            note="Registered via Client Portal",
            on_hold_expire_duration=None,
            on_hold_timeout=None,
            auto_delete_in_days=None, # Consider making this configurable
            next_plan=None
        )
        print(f"[DEBUG] UserCreate payload for {generated_account_number}: {user_payload.model_dump_json(indent=2)}")

        print("[DEBUG] Attempting to create user in database")
        # Portal users are not directly created by a specific admin, so admin=None
        new_db_user = crud.create_user(db=db, account_number=generated_account_number, user=user_payload, admin=None)
        print(f"[DEBUG] User created successfully with ID: {new_db_user.id} for account {generated_account_number}")

        print(f"[DEBUG] Creating access token for {generated_account_number}")
        access_token = create_access_token(data={"sub": new_db_user.account_number})
        print(f"[DEBUG] Access token created successfully for {generated_account_number}")

        redirect_url = request.url_for("portal_account_page") # Ensure this route name is correct
        print(f"[DEBUG] Generated redirect URL: {redirect_url} for {generated_account_number}")

        response = RedirectResponse(url=redirect_url, status_code=303)
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            path='/',
            samesite='Lax',
            secure=request.url.scheme == "https",
            max_age=1800, # 30 minutes
            domain=None # Let the browser determine the domain
        )
        print(f"[DEBUG] Cookie set successfully for {generated_account_number}")
        return response

    except Exception as e:
        print(f"[DEBUG] Error during registration for {generated_account_number}: {str(e)}")
        import traceback
        print(f"[DEBUG] Full traceback for {generated_account_number}:\n{traceback.format_exc()}")
        # It's crucial to return an error response to the client
        return templates.TemplateResponse(
            "register.html", # Render the registration page again with an error
            {"request": request, "error": f"Could not create account due to an internal error. Please try again later or contact support."},
            status_code=500
        )


@router.get("/logout", name="portal_logout")
async def logout_and_redirect(request: Request, response: Response):
    redirect_response = RedirectResponse(url=request.url_for("portal_login_page"), status_code=303)
    redirect_response.delete_cookie(key="access_token", path='/') # Changed from '/client-portal' to '/'
    return redirect_response