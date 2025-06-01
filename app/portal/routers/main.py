from fastapi import APIRouter, Depends, Request, HTTPException, BackgroundTasks, Response as FastAPIResponse
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
# import httpx # Keep if other parts use it, though not for local node fetching
import os
import stripe # type: ignore
import re
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import uuid

from app import logger, xray
from app.db import get_db, crud
from app.db.models import User as DBUser
from app.portal.models.plan import Plan
from app.portal.auth import get_current_user, get_current_user_optional # Assuming these are your auth dependencies
# from app.models.admin import Admin # Pydantic Admin, not directly used in this router
from app.models.user import UserResponse, UserStatus, UserModify, UserStatusModify # UserStatusCreate removed as not used
from app.models.node import NodeStatus # Import NodeStatus for filtering
# from app.models.node import NodeResponse # Not strictly needed if template uses ORM node attributes

from config import MOCK_STRIPE_PAYMENT as APP_MOCK_STRIPE_PAYMENT


# --- Environment Variables & Configuration ---
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

MOCK_STRIPE_PAYMENT = APP_MOCK_STRIPE_PAYMENT

logger.info(f"INITIAL MODULE LOAD (portal/main.py): MOCK_STRIPE_PAYMENT (Python) = {MOCK_STRIPE_PAYMENT}")
logger.info(f"INITIAL MODULE LOAD (portal/main.py): STRIPE_PUBLIC_KEY (Python) = '{STRIPE_PUBLIC_KEY}'")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000") # Default if not set

if not MOCK_STRIPE_PAYMENT and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
elif not MOCK_STRIPE_PAYMENT and not STRIPE_SECRET_KEY:
    logger.warning("Stripe secret key not found and not in mock payment mode. Real payments will fail.")


router = APIRouter(prefix="/client-portal", tags=["Client Portal"])
templates = Jinja2Templates(directory="app/portal/templates")
templates.env.globals['datetime'] = datetime
templates.env.globals['UserStatus'] = UserStatus # For using UserStatus.value in templates
templates.env.globals["os"] = os # If you need os module in templates

# --- Jinja Filters ---
def readable_bytes_filter(size_in_bytes):
    if size_in_bytes is None: return "Unlimited"
    if not isinstance(size_in_bytes, (int, float)) or size_in_bytes < 0: return "0 B"
    if size_in_bytes == 0: return "0 B" # Can mean 0 allowed or truly 0, context matters
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    # Ensure size_in_bytes is float for division if it's an int
    size_in_bytes_float = float(size_in_bytes)
    while size_in_bytes_float >= 1024.0 and i < len(units) - 1:
        size_in_bytes_float /= 1024.0
        i += 1
    return f"{size_in_bytes_float:.1f} {units[i]}"

def timestamp_to_datetime_str_filter(timestamp, format_str="%Y-%m-%d %H:%M UTC"): # Renamed format to format_str
    if timestamp is None: return "N/A"
    try:
        # Ensure timestamp is treated as UTC if it's naive
        dt_obj = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
        return dt_obj.strftime(format_str)
    except (ValueError, TypeError, OSError):
        return "Invalid Date"

def time_until_expiry_filter(timestamp):
    if timestamp is None: return "Never"
    try:
        now_utc = datetime.now(timezone.utc) # Use timezone-aware now
        expire_dt_utc = datetime.fromtimestamp(int(timestamp), tz=timezone.utc) # Assume timestamp is UTC

        if now_utc >= expire_dt_utc:
            return "Expired"

        delta = expire_dt_utc - now_utc
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        if days > 365: return f"{days // 365} years" # Approximation
        if days > 60: return f"{days // 30} months" # Approximation
        if days > 0: return f"{days} days" + (f", {hours} hrs" if days < 7 and hours > 0 else "")
        if hours > 0: return f"{hours} hours" + (f", {minutes} min" if minutes > 0 else "")
        if minutes > 0: return f"{minutes} minutes"
        return "Less than a minute"
    except (ValueError, TypeError, OSError) as e:
        logger.error(f"Error in time_until_expiry_filter for timestamp {timestamp}: {e}")
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

    new_data_limit = db_user_orm.data_limit
    if plan.data_limit is not None:
        new_data_limit = plan.data_limit if plan.data_limit >= 0 else None # Ensure 0 is handled, None for unlimited

    new_expire = db_user_orm.expire
    current_expire_dt = datetime.now(timezone.utc)
    if db_user_orm.expire and db_user_orm.expire > current_expire_dt.timestamp() : # if current plan is active
        current_expire_dt = datetime.fromtimestamp(db_user_orm.expire, tz=timezone.utc)

    if plan.duration_days is not None:
        if plan.duration_days > 0:
            new_expire_dt = (current_expire_dt if current_expire_dt > datetime.now(timezone.utc) else datetime.now(timezone.utc)) + timedelta(days=plan.duration_days)
            new_expire = int(new_expire_dt.timestamp())
        elif plan.duration_days == 0: # Explicitly means remove expiry / make unlimited time
            new_expire = None
        # If plan.duration_days is negative, new_expire remains unchanged (db_user_orm.expire)

    # Build the UserModify payload
    user_modify_payload_dict: Dict[str, Any] = { # Explicitly type hint for clarity
        "status": UserStatusModify.active,
        "data_limit": new_data_limit,
        "expire": new_expire,
        "on_hold_expire_duration": None,
        "on_hold_timeout": None,
        "note": db_user_orm.note, # Preserve existing note
        "data_limit_reset_strategy": db_user_orm.data_limit_reset_strategy, # Preserve existing strategy
    }

    # Filter for only fields present in UserModify model to avoid errors
    valid_user_modify_fields = UserModify.model_fields.keys()
    filtered_payload_dict = {k: v for k, v in user_modify_payload_dict.items() if k in valid_user_modify_fields}

    try:
        user_modify_payload = UserModify(**filtered_payload_dict)
    except Exception as e:
        logger.error(f"activate_user_plan: Pydantic validation error for UserModify for user {user_account_number}: {e}. Payload: {filtered_payload_dict}", exc_info=True)
        return False

    try:
        updated_user_orm = crud.update_user(db=db, dbuser=db_user_orm, modify=user_modify_payload)

        # If traffic reset is desired upon plan activation (e.g., new data limit applied)
        # and the plan implies it, you might call it here.
        if plan.data_limit is not None: # Or some other condition indicating traffic reset
            logger.info(f"activate_user_plan: Plan includes data limit, resetting traffic for user {user_account_number}.")
            updated_user_orm = crud.reset_user_data_usage(db=db, dbuser=updated_user_orm) # Returns the updated user

        # Ensure user has all default proxy types
        logger.info(f"activate_user_plan: Ensuring default proxy types for user {user_account_number}")
        crud.ensure_all_default_proxies_for_user(db=db, user_id=updated_user_orm.id)

        # Refresh the user object to get the updated proxies
        db.refresh(updated_user_orm)
        user_response_for_xray = UserResponse.model_validate(updated_user_orm)

        background_tasks.add_task(xray.operations.update_user, user_id=updated_user_orm.id)

        logger.info(f"activate_user_plan: User {user_account_number} processed for plan {plan_id}. Xray update task scheduled.")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"activate_user_plan: Error updating user {user_account_number} or scheduling Xray: {e}", exc_info=True)
        return False


# --- Route Handlers ---
@router.get("/", response_class=HTMLResponse, name="portal_home")
async def portal_home(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[DBUser] = Depends(get_current_user_optional) # Use DBUser for consistency
):
    plans_data = [
        get_plan_by_id("basic"),
        get_plan_by_id("premium"),
        get_plan_by_id("unlimited")
    ]
    # Filter out None plans if get_plan_by_id can return None
    plans_data = [p for p in plans_data if p]


    # If user is authenticated, convert to Pydantic for template if needed, or pass ORM
    user_for_template = UserResponse.model_validate(current_user) if current_user else None

    if user_for_template and user_for_template.status == UserStatus.disabled:
        return RedirectResponse(url=request.url_for("portal_account_page"), status_code=303) # Use named route

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "plans": plans_data,
            "current_user": user_for_template, # Pass Pydantic UserResponse or None
            "STRIPE_PUBLIC_KEY": STRIPE_PUBLIC_KEY,
            "MOCK_STRIPE_PAYMENT": MOCK_STRIPE_PAYMENT
        }
    )

@router.get("/account", response_class=HTMLResponse, name="portal_account_page")
async def portal_account_page( # Renamed route function
    request: Request,
    db: Session = Depends(get_db),
    current_user_orm: DBUser = Depends(get_current_user) # Ensure this returns ORM user
):
    # current_user_orm is already fetched by dependency, includes eager loads like active_node
    user_info_for_template = UserResponse.model_validate(current_user_orm)

    plans_data = [p for p in [get_plan_by_id("basic"), get_plan_by_id("premium"), get_plan_by_id("unlimited")] if p]

    # Nodes data for potential display (e.g. dropdown for manual activation if we add it later)
    # For now, active node is managed on servers page.
    # nodes_data = [NodeResponse.model_validate(n) for n in crud.get_nodes(db, status=NodeStatus.connected)]

    subscription_token = ""
    # Logic to extract token from subscription_url more robustly
    if user_info_for_template.subscription_url:
        try:
            # Example: /sub/00000000-0000-0000-0000-000000000000
            #          /sub/00000000-0000-0000-0000-000000000000/
            #          /sub/00000000-0000-0000-0000-000000000000/clash
            match = re.search(r"/sub/([a-fA-F0-9-]+)", user_info_for_template.subscription_url)
            if match:
                subscription_token = match.group(1)
        except Exception as e:
            logger.warning(f"Error parsing subscription token from URL '{user_info_for_template.subscription_url}': {e}")


    subscription_url_base = ""
    if subscription_token:
        try:
            # Ensure the 'user_subscription' route name is correct as defined in app.routers.subscription
            subscription_url_base = str(request.url_for('user_subscription', token=subscription_token))
        except Exception as e: # Catch runtime error if route not found by that name
            logger.error(f"Could not generate subscription_url_base for token '{subscription_token}': {e}. Route 'user_subscription' might be missing or misnamed.")
            # Fallback to manual construction if url_for fails (less ideal)
            if "/sub/" in user_info_for_template.subscription_url:
                 parts = user_info_for_template.subscription_url.split('/sub/')
                 if len(parts) > 1:
                     base_part = request.base_url # Use request's base URL
                     # Correctly join parts to form the base URL for subscription
                     subscription_url_base = f"{str(base_part).rstrip('/')}/{XRAY_SUBSCRIPTION_PATH.strip('/')}/{subscription_token}"


    return templates.TemplateResponse(
        "account.html",
        {
            "request": request,
            "current_user": user_info_for_template, # Pydantic UserResponse
            "plans": plans_data,
            # "nodes": nodes_data, # Not passing nodes here, handled by /servers page
            "STRIPE_PUBLIC_KEY": STRIPE_PUBLIC_KEY,
            "subscription_url_base": subscription_url_base.rstrip('/'),
            "MOCK_STRIPE_PAYMENT": MOCK_STRIPE_PAYMENT,
        }
    )

@router.get("/servers", response_class=HTMLResponse, name="portal_servers_page")
async def portal_servers_page( # Renamed route function
    request: Request,
    db: Session = Depends(get_db),
    current_user_orm: DBUser = Depends(get_current_user) # Use ORM from auth dependency
):
    # Fetch only nodes that users can potentially connect to.
    # Admins might see all nodes in their dashboard, but users see connectable ones.
    nodes_for_display = crud.get_nodes(db, status=[NodeStatus.connected, NodeStatus.connecting, NodeStatus.error])
    # NodeStatus.error might be included to show it's temporarily down.
    # NodeStatus.connecting might also be shown.
    # The template logic will disable "Activate" for non-connected nodes.

    # Pass ORM current_user to template, which will have active_node_id and account_number.
    # The template can then use current_user_orm.active_node_id directly.
    return templates.TemplateResponse(
        "servers.html",
        {
            "request": request,
            "nodes": nodes_for_display, # List of ORM Node objects
            "current_user": current_user_orm, # Pass ORM User object
            # "NodeStatus": NodeStatus # No longer needed if template uses node.status.value
        }
    )

@router.post("/create-checkout-session", name="create_checkout_session")
async def create_checkout_session(
    request: Request,
    plan_id_data: dict, # Expecting {"plan_id": "basic"}
    db: Session = Depends(get_db),
    current_user_orm: DBUser = Depends(get_current_user), # Use ORM for consistency
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
        logger.info(f"Mock payment mode: Simulating payment for user {current_user_orm.account_number}, plan {plan_id}")
        activation_success = await activate_user_plan(
            db, current_user_orm.account_number, plan_id, background_tasks
        )
        # Use named route for redirect URL
        redirect_url_base = str(request.url_for("portal_account_page"))
        if activation_success:
            redirect_url = f"{redirect_url_base}?payment_status=mock_success"
            return JSONResponse({'url': redirect_url, 'mock': True})
        else:
            logger.error(f"Mock payment mode: Failed to activate plan for user {current_user_orm.account_number}")
            redirect_url = f"{redirect_url_base}?payment_status=mock_failure"
            return JSONResponse({'url': redirect_url, 'mock': True, 'error': 'Mock activation failed'}, status_code=500)

    if not STRIPE_SECRET_KEY or not STRIPE_PUBLIC_KEY: # Guard against missing keys
        logger.error("Stripe keys are not configured for live checkout session.")
        raise HTTPException(status_code=500, detail="Payment system not configured.")
    if not stripe.api_key: stripe.api_key = STRIPE_SECRET_KEY # Ensure it's set for this call

    if not plan.stripe_price_id or "_placeholder" in plan.stripe_price_id:
        logger.error(f"Stripe Price ID not configured for plan {plan.name}: {plan.stripe_price_id}")
        raise HTTPException(status_code=500, detail="Payment plan configuration error.")

    success_url = str(request.url_for("portal_account_page")) + "?payment_status=success&session_id={CHECKOUT_SESSION_ID}"
    cancel_url = str(request.url_for("portal_account_page")) + "?payment_status=cancelled"

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': plan.stripe_price_id, 'quantity': 1}],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=current_user_orm.account_number, # Link session to user
            metadata={'plan_id': plan.id, 'user_account_number': current_user_orm.account_number}
        )
        return JSONResponse({'url': checkout_session.url, 'mock': False})
    except stripe.error.StripeError as e:
        logger.error(f"Stripe Checkout Error for user {current_user_orm.account_number}: {e.user_message or str(e)}")
        raise HTTPException(status_code=500, detail=f"Payment gateway error: {e.user_message or 'Please try again later.'}")
    except Exception as e:
        logger.error(f"Generic Error creating checkout session for user {current_user_orm.account_number}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred with payment processing.")


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
        return JSONResponse({"status": "error", "detail":"Webhook secret not configured"}, status_code=500) # Return 500 so Stripe retries if temp issue
    if not stripe.api_key: stripe.api_key = STRIPE_SECRET_KEY

    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    event = None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError as e: # Invalid payload
        logger.error(f"Stripe webhook ValueError (invalid payload): {e}")
        return JSONResponse({"status": "error", "detail": "Invalid payload"}, status_code=400)
    except stripe.error.SignatureVerificationError as e: # Invalid signature
        logger.error(f"Stripe webhook SignatureVerificationError (invalid signature): {e}")
        return JSONResponse({"status": "error", "detail": "Invalid signature"}, status_code=400)
    except Exception as e:
        logger.error(f"Stripe webhook construct_event generic error: {e}")
        return JSONResponse({"status": "error", "detail": "Webhook processing error"}, status_code=500)


    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        # According to Stripe docs, for 'payment' mode, check payment_status.
        # For 'subscription' mode, status would be 'complete' if initial payment succeeded.
        # Here, we're using 'payment' mode.
        if session.get('mode') == 'payment' and session.get('payment_status') == 'paid':
            user_account_number = session.get('client_reference_id')
            plan_id_from_meta = session.get('metadata', {}).get('plan_id')

            if not user_account_number or not plan_id_from_meta:
                logger.error("Webhook (checkout.session.completed): Missing user_account_number or plan_id in Stripe session metadata.")
                # Return 200 to Stripe to acknowledge receipt but log error, as this data won't magically appear.
                return JSONResponse({"status": "error_missing_data_acknowledged"}, status_code=200)

            logger.info(f"Webhook: Payment successful for user {user_account_number}, plan {plan_id_from_meta}. Activating plan.")
            activation_success = await activate_user_plan(db, user_account_number, plan_id_from_meta, background_tasks)

            if not activation_success:
                logger.error(f"Webhook: Failed to activate plan {plan_id_from_meta} for user {user_account_number} after successful payment.")
                # This is an internal error. Stripe should ideally retry if this is a 5xx.
                return JSONResponse({"status": "error_plan_activation_failed"}, status_code=500)
            logger.info(f"Webhook: Plan {plan_id_from_meta} successfully activated for user {user_account_number}.")
        else:
            logger.info(f"Webhook: Checkout session {session.id} completed but payment_status is '{session.get('payment_status')}' (mode: {session.get('mode')}). No action taken.")

    # Acknowledge other event types if necessary, or just return 200 for unhandled ones.
    return JSONResponse({"status": "received_and_processed_ok"}, status_code=200)


# Ensure get_plan_by_id is robust
def get_plan_by_id(plan_id: str) -> Optional[Plan]:
    """Get a plan by its ID."""
    # This should ideally fetch from a database or a more dynamic config source.
    # For now, using the hardcoded dict:
    plans_config = {
        "basic": Plan(
            id="basic", name="Basic Plan", description="Perfect for individual users", price=9.99, duration_days=30,
            data_limit=100 * 1024 * 1024 * 1024, stripe_price_id=os.getenv("STRIPE_PRICE_ID_BASIC"), # Get from env
            features=["1 Device", "100GB Data", "30 Days"]
        ),
        "premium": Plan(
            id="premium", name="Premium Plan", description="For power users and small families", price=19.99, duration_days=30,
            data_limit=500 * 1024 * 1024 * 1024, stripe_price_id=os.getenv("STRIPE_PRICE_ID_PREMIUM"),
            features=["3 Devices", "500GB Data", "30 Days"]
        ),
        "unlimited": Plan(
            id="unlimited", name="Unlimited Plan", description="Unlimited data for heavy users", price=29.99, duration_days=30,
            data_limit=None, stripe_price_id=os.getenv("STRIPE_PRICE_ID_UNLIMITED"), # data_limit=None for unlimited
            features=["5 Devices", "Unlimited Data", "30 Days"]
        )
    }
    found_plan = plans_config.get(plan_id)

    return found_plan

# Example of XRAY_SUBSCRIPTION_PATH from config, if needed for url_for fallback in account_page
try:
    from config import XRAY_SUBSCRIPTION_PATH
except ImportError:
    XRAY_SUBSCRIPTION_PATH = "sub" # Default fallback