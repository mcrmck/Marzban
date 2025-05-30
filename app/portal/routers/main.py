from fastapi import APIRouter, Depends, Request, HTTPException, BackgroundTasks, Response as FastAPIResponse
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import httpx # Keep if other parts use it, though not for local node fetching
import os
import stripe
from typing import Optional, List
from datetime import datetime, timedelta
import uuid

from app import logger, xray
from app.db import get_db, crud
from app.db.models import User as DBUser
from app.portal.models.plan import Plan
from app.portal.auth import get_current_user, get_current_user_optional
from app.models.admin import Admin # Assuming Pydantic model
from app.models.user import UserResponse, UserStatus, UserModify, UserStatusCreate, UserStatusModify # Ensure UserStatusModify is imported
from app.models.node import NodeResponse
# Assuming MOCK_STRIPE_PAYMENT is correctly imported or defined in config.py and then imported here
# If it's directly in config.py and you want to use it here:
from config import MOCK_STRIPE_PAYMENT as APP_MOCK_STRIPE_PAYMENT


# --- Environment Variables & Configuration ---
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

MOCK_STRIPE_PAYMENT = APP_MOCK_STRIPE_PAYMENT

logger.info(f"INITIAL MODULE LOAD (main.py): MOCK_STRIPE_PAYMENT (Python) = {MOCK_STRIPE_PAYMENT}")
logger.info(f"INITIAL MODULE LOAD (main.py): STRIPE_PUBLIC_KEY (Python) = '{STRIPE_PUBLIC_KEY}'")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000")

if not MOCK_STRIPE_PAYMENT and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
elif not MOCK_STRIPE_PAYMENT and not STRIPE_SECRET_KEY:
    logger.warning("Stripe secret key not found and not in mock payment mode. Real payments will fail.")


router = APIRouter(prefix="/client-portal", tags=["Client Portal"])
templates = Jinja2Templates(directory="app/portal/templates")
templates.env.globals['datetime'] = datetime
templates.env.globals['UserStatus'] = UserStatus
templates.env.globals["os"] = os

# --- Jinja Filters ---
def readable_bytes_filter(size_in_bytes):
    if size_in_bytes is None: return "Unlimited"
    if not isinstance(size_in_bytes, (int, float)) or size_in_bytes < 0: return "0 B"
    if size_in_bytes == 0: return "0 B"
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    while size_in_bytes >= 1024 and i < len(units) - 1:
        size_in_bytes /= 1024.0
        i += 1
    return f"{size_in_bytes:.1f} {units[i]}"

def timestamp_to_datetime_str_filter(timestamp, format="%Y-%m-%d %H:%M UTC"):
    if timestamp is None: return "N/A"
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timedelta(0)).strftime(format)
    except (ValueError, TypeError, OSError):
        return "Invalid Date"

def time_until_expiry_filter(timestamp):
    if timestamp is None: return "Never"
    try:
        now_utc = datetime.utcnow()
        expire_dt_utc = datetime.fromtimestamp(int(timestamp))

        if now_utc >= expire_dt_utc:
            return "Expired"

        delta = expire_dt_utc - now_utc
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        if days > 0:
            return f"{days} days" + (f", {hours} hrs" if days < 7 and hours > 0 else "")
        elif hours > 0:
            return f"{hours} hours" + (f", {minutes} min" if minutes > 0 else "")
        elif minutes > 0:
            return f"{minutes} minutes"
        return "Less than a minute"
    except (ValueError, TypeError, OSError):
        return "Invalid Expiry"

templates.env.filters["readable_bytes"] = readable_bytes_filter
templates.env.filters["timestamp_to_datetime_str"] = timestamp_to_datetime_str_filter
templates.env.filters["time_until_expiry"] = time_until_expiry_filter

# --- Helper function to activate user plan ---
async def activate_user_plan(
    db: Session,
    user_account_number: str,
    plan_id: str,
    background_tasks: BackgroundTasks
):
    db_user_orm = crud.get_user(db, account_number=user_account_number)
    if not db_user_orm:
        logger.error(f"activate_user_plan: User {user_account_number} not found.")
        return False

    plan = get_plan_by_id(plan_id)
    if not plan:
        logger.error(f"activate_user_plan: Plan {plan_id} not found for user {user_account_number}.")
        return False

    update_data = {
        "status": UserStatusModify.active,
        "data_limit": plan.data_limit if plan.data_limit is not None else db_user_orm.data_limit,
        "expire": int((datetime.utcnow() + timedelta(days=plan.duration_days)).timestamp()) if plan.duration_days and plan.duration_days > 0 else None,
        "used_traffic": 0,
        "on_hold_expire_duration": None,
        "on_hold_timeout": None,
        # Proxies and inbounds will be taken from the existing user,
        # unless the plan dictates specific changes (not implemented here)
    }

    current_user_pydantic = UserResponse.model_validate(db_user_orm)
    payload_for_update = current_user_pydantic.model_dump(exclude_unset=True)
    payload_for_update.update(update_data)

    valid_modify_fields = UserModify.model_fields.keys()
    final_payload_dict = {}
    for field_name in valid_modify_fields:
        if field_name in payload_for_update:
            model_field = UserModify.model_fields[field_name]
            is_optional = hasattr(model_field.annotation, '__origin__') and model_field.annotation.__origin__ is Optional \
                          or (hasattr(model_field.annotation, '__args__') and type(None) in model_field.annotation.__args__)

            if payload_for_update[field_name] is not None or is_optional:
                 final_payload_dict[field_name] = payload_for_update[field_name]
            elif not is_optional and payload_for_update[field_name] is None:
                logger.warning(f"activate_user_plan: Required field '{field_name}' became None for UserModify. This might cause issues if UserModify doesn't allow it to be None.")
                # If UserModify requires this field, Pydantic will raise an error.
                # For now, we pass it as is, assuming UserModify handles it or it's truly optional.
                final_payload_dict[field_name] = payload_for_update[field_name]


    try:
        user_modify_payload = UserModify(**final_payload_dict)
    except Exception as e:
        logger.error(f"activate_user_plan: Pydantic validation error for UserModify for user {user_account_number}: {e}. Payload: {final_payload_dict}")
        return False

    try:
        # ***** THE FIX IS HERE *****
        updated_user_orm = crud.update_user(db=db, dbuser=db_user_orm, modify=user_modify_payload)
        # ***************************

        background_tasks.add_task(xray.operations.add_user, dbuser=updated_user_orm)
        logger.info(f"activate_user_plan: User {user_account_number} processed for plan {plan_id}. Xray task scheduled.")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"activate_user_plan: Error updating user {user_account_number} in DB or scheduling Xray: {e}", exc_info=True) # Added exc_info for full traceback
        return False


# --- Route Handlers ---
@router.get("/", response_class=HTMLResponse, name="portal_home")
async def portal_home(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    plans_data = [
        get_plan_by_id("basic"),
        get_plan_by_id("premium"),
        get_plan_by_id("unlimited")
    ]

    if current_user and current_user.status == UserStatus.disabled:
        return RedirectResponse(url=request.url_for("account_page"), status_code=303)

    logger.info(f"[DEBUG] portal_home: Python MOCK_STRIPE_PAYMENT = {MOCK_STRIPE_PAYMENT}")
    logger.info(f"[DEBUG] portal_home: Python STRIPE_PUBLIC_KEY = '{STRIPE_PUBLIC_KEY}'")

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "plans": plans_data,
            "current_user": current_user,
            "STRIPE_PUBLIC_KEY": STRIPE_PUBLIC_KEY,
            "MOCK_STRIPE_PAYMENT": MOCK_STRIPE_PAYMENT
        }
    )

@router.get("/account", response_class=HTMLResponse, name="account_page")
async def account_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    user_db_orm = crud.get_user(db, account_number=current_user.account_number)
    if not user_db_orm:
        logger.warning(f"Account page: User {current_user.account_number} found via token but not in DB. Redirecting to login.")
        response = RedirectResponse(url=request.url_for("login_page"), status_code=303)
        response.delete_cookie(key="access_token", path='/client-portal')
        return response

    user_info_for_template = UserResponse.model_validate(user_db_orm)

    plans_data = [
        get_plan_by_id("basic"),
        get_plan_by_id("premium"),
        get_plan_by_id("unlimited")
    ]

    nodes_data = []
    if user_info_for_template.status == UserStatus.active:
        try:
            all_nodes_orm = crud.get_nodes(db)
            if all_nodes_orm:
                nodes_data = [NodeResponse.model_validate(n) for n in all_nodes_orm]
        except Exception as e:
            logger.error(f"Error fetching nodes for account page: {e}")
            nodes_data = []

    subscription_token = ""
    if user_info_for_template.subscription_url:
        path_parts = user_info_for_template.subscription_url.split('?')[0].split('#')[0].strip('/').split('/')
        if len(path_parts) > 0 :
            try:
                sub_index = path_parts.index("sub")
                if sub_index + 1 < len(path_parts):
                    potential_token = path_parts[sub_index+1]
                    if len(potential_token) > 20 and potential_token.replace('-', '').isalnum():
                         subscription_token = potential_token
            except ValueError:
                if path_parts[-1] != "info" and len(path_parts[-1]) > 20 and path_parts[-1].replace('-', '').isalnum():
                    subscription_token = path_parts[-1]

    subscription_url_base = ""
    if subscription_token:
        try:
            subscription_url_base = str(request.url_for('user_subscription', token=subscription_token))
        except Exception as e:
            logger.warning(f"Could not generate subscription_url_base for token '{subscription_token}' using url_for('user_subscription'): {e}. Falling back.")
            if "/sub/" in user_info_for_template.subscription_url:
                parts = user_info_for_template.subscription_url.split('/sub/')
                if len(parts) > 1:
                    base_part = parts[0]
                    token_part = parts[1].split('/')[0]
                    if token_part == subscription_token:
                         subscription_url_base = f"{base_part}/sub/{token_part}"

    logger.info(f"[DEBUG] account_page: Python MOCK_STRIPE_PAYMENT = {MOCK_STRIPE_PAYMENT}")
    logger.info(f"[DEBUG] account_page: Python STRIPE_PUBLIC_KEY = '{STRIPE_PUBLIC_KEY}'")

    return templates.TemplateResponse(
        "account.html",
        {
            "request": request,
            "current_user": user_info_for_template,
            "plans": plans_data,
            "nodes": nodes_data,
            "STRIPE_PUBLIC_KEY": STRIPE_PUBLIC_KEY,
            "subscription_url_base": subscription_url_base.rstrip('/'),
            "MOCK_STRIPE_PAYMENT": MOCK_STRIPE_PAYMENT
        }
    )

@router.get("/servers", response_class=HTMLResponse, name="servers_page")
async def servers_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional)
):
    nodes_data = []
    try:
        all_nodes_orm = crud.get_nodes(db)
        if all_nodes_orm:
             nodes_data = [NodeResponse.model_validate(n) for n in all_nodes_orm]
    except Exception as e:
        logger.error(f"Error fetching nodes for servers_page: {e}")
        nodes_data = []

    return templates.TemplateResponse(
        "servers.html",
        {"request": request, "nodes": nodes_data, "current_user": current_user}
    )

@router.post("/create-checkout-session", name="create_checkout_session")
async def create_checkout_session(
    request: Request,
    plan_id_data: dict,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    logger.info(f"[DEBUG] create_checkout_session: Python MOCK_STRIPE_PAYMENT = {MOCK_STRIPE_PAYMENT}")

    plan_id = plan_id_data.get("plan_id")
    if not plan_id:
        raise HTTPException(status_code=400, detail="Plan ID is required.")

    plan = get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")

    if MOCK_STRIPE_PAYMENT:
        logger.info(f"Mock payment mode: Simulating payment for user {current_user.account_number}, plan {plan_id}")
        activation_success = await activate_user_plan(
            db, current_user.account_number, plan_id, background_tasks
        )
        redirect_url_base = str(request.url_for("account_page"))
        if activation_success:
            redirect_url = f"{redirect_url_base}?payment_status=mock_success"
            return JSONResponse({'url': redirect_url, 'mock': True})
        else:
            logger.error(f"Mock payment mode: Failed to activate plan for user {current_user.account_number}")
            redirect_url = f"{redirect_url_base}?payment_status=mock_failure"
            return JSONResponse({'url': redirect_url, 'mock': True, 'error': 'Mock activation failed'}, status_code=500)

    if not STRIPE_SECRET_KEY or not STRIPE_PUBLIC_KEY:
        logger.error("Stripe keys are not configured for checkout session.")
        raise HTTPException(status_code=500, detail="Stripe keys are not configured.")
    if not stripe.api_key:
        logger.error("Stripe API key not initialized.")
        raise HTTPException(status_code=500, detail="Stripe API key not initialized.")

    if not plan.stripe_price_id or "_placeholder" in plan.stripe_price_id:
        logger.error(f"Stripe Price ID not configured or is a placeholder for plan {plan.name}: {plan.stripe_price_id}")
        raise HTTPException(status_code=500, detail=f"Stripe Price ID not configured for plan {plan.name}.")

    success_url = str(request.url_for("account_page")) + "?payment_status=success&session_id={CHECKOUT_SESSION_ID}"
    cancel_url = str(request.url_for("account_page")) + "?payment_status=cancelled"

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': plan.stripe_price_id, 'quantity': 1}],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=current_user.account_number,
            metadata={'plan_id': plan.id, 'user_account_number': current_user.account_number }
        )
        return JSONResponse({'url': checkout_session.url, 'mock': False})
    except stripe.error.StripeError as e:
        logger.error(f"Stripe Checkout Error: {e.user_message or str(e)}")
        raise HTTPException(status_code=500, detail=f"Could not create Stripe checkout session: {e.user_message or str(e)}")
    except Exception as e:
        logger.error(f"Generic Error creating checkout session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@router.post("/stripe-webhook", include_in_schema=False, name="stripe_webhook")
async def stripe_webhook_handler(
    request: Request,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    if MOCK_STRIPE_PAYMENT:
        logger.info("Stripe webhook endpoint called in mock payment mode. Ignoring.")
        return JSONResponse({"status": "ignored_mock_mode"}, status_code=200)

    if not STRIPE_WEBHOOK_SECRET:
        logger.error("Stripe webhook secret not configured.")
        raise HTTPException(status_code=500, detail="Webhook secret not configured.")
    if not stripe.api_key:
        logger.error("Stripe API key not initialized for webhook.")
        raise HTTPException(status_code=500, detail="Stripe API key not initialized.")

    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    event = None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError as e:
        logger.error(f"Stripe webhook ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Stripe webhook SignatureVerificationError: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        if session.mode == 'payment' and session.payment_status != 'paid':
            logger.info(f"Webhook: Checkout session {session.id} for user {session.client_reference_id} not paid yet (status: {session.payment_status}). Skipping.")
            return JSONResponse({"status": "skipped", "detail": "Session not paid"}, status_code=200)

        user_account_number = session.get('client_reference_id')
        plan_id = session.get('metadata', {}).get('plan_id')

        if not user_account_number or not plan_id:
            logger.error("Webhook: Missing user_account_number or plan_id in Stripe session.")
            return JSONResponse({"status": "error", "detail": "Missing data in session"}, status_code=400)

        activation_success = await activate_user_plan(db, user_account_number, plan_id, background_tasks)
        if not activation_success:
            # Consider the type of error. If it's something Stripe should retry (like a temporary DB issue),
            # returning 500 is appropriate. If it's a permanent issue (user not found), 200 might be better
            # to prevent Stripe from retrying indefinitely for a non-recoverable error on our end.
            # For now, 500 to indicate our server had an issue processing.
            return JSONResponse({"status": "error", "detail": "Failed to activate user plan"}, status_code=500)

    return JSONResponse({"status": "received"}, status_code=200)

def get_plan_by_id(plan_id: str) -> Optional[Plan]:
    """Get a plan by its ID."""
    plans = {
        "basic": Plan(
            id="basic", name="Basic Plan", description="Perfect for individual users", price=9.99, duration_days=30,
            data_limit=100 * 1024 * 1024 * 1024, stripe_price_id=os.getenv("STRIPE_PRICE_ID_BASIC", "price_basic_placeholder"),
            features=["1 Device", "100GB Data", "30 Days"]
        ),
        "premium": Plan(
            id="premium", name="Premium Plan", description="For power users and small families", price=19.99, duration_days=30,
            data_limit=500 * 1024 * 1024 * 1024, stripe_price_id=os.getenv("STRIPE_PRICE_ID_PREMIUM", "price_premium_placeholder"),
            features=["3 Devices", "500GB Data", "30 Days"]
        ),
        "unlimited": Plan(
            id="unlimited", name="Unlimited Plan", description="Unlimited data for heavy users", price=29.99, duration_days=30,
            data_limit=None, stripe_price_id=os.getenv("STRIPE_PRICE_ID_UNLIMITED", "price_unlimited_placeholder"),
            features=["5 Devices", "Unlimited Data", "30 Days"]
        )
    }
    found_plan = plans.get(plan_id)
    if found_plan and (not found_plan.stripe_price_id or "_placeholder" in found_plan.stripe_price_id):
        logger.warning(f"Plan '{plan_id}' is using a placeholder or missing Stripe Price ID: {found_plan.stripe_price_id}")
    return found_plan
