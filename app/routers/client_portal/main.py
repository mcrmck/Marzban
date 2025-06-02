from fastapi import APIRouter, Depends, Request, HTTPException, BackgroundTasks, Response as FastAPIResponse, status
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
from app.routers.client_portal.auth_utils import get_current_user, get_current_user_optional, create_access_token
# from app.models.admin import Admin # Pydantic Admin, not directly used in this router
from app.models.user import UserResponse, UserStatus, UserModify, UserStatusModify, UserCreate, UserStatusCreate, ProxyTypes
from app.models.node import NodeStatus, NodeResponse  # Added NodeResponse import
# from app.models.node import NodeResponse # Not strictly needed if template uses ORM node attributes
from app.models.plan import PlanResponse
from app.portal.plans import get_plan_by_id
from app.portal.models.api import PortalAccountDetailsResponse, ClientLoginRequest, TokenResponse

from config import MOCK_STRIPE_PAYMENT as APP_MOCK_STRIPE_PAYMENT


# --- Environment Variables & Configuration ---
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

MOCK_STRIPE_PAYMENT = APP_MOCK_STRIPE_PAYMENT


FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000") # Default if not set

if not MOCK_STRIPE_PAYMENT and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
elif not MOCK_STRIPE_PAYMENT and not STRIPE_SECRET_KEY:
    logger.warning("Stripe secret key not found and not in mock payment mode. Real payments will fail.")


router = APIRouter(tags=["Client Portal API"])
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
async def _activate_user_plan(
    db: Session,
    user_account_number: str,
    plan_id: str,
    background_tasks: BackgroundTasks
):
    """
    Core business logic for activating a user's plan.
    This function handles the actual plan activation process including:
    - Updating user status and limits
    - Configuring proxies
    - Scheduling background tasks

    Args:
        db: Database session
        user_account_number: The user's account number
        plan_id: The ID of the plan to activate
        background_tasks: FastAPI background tasks for async operations

    Returns:
        bool: True if activation was successful, False otherwise
    """
    db_user_orm = crud.get_user(db, account_number=user_account_number)
    if not db_user_orm:
        logger.error(f"_activate_user_plan: User {user_account_number} not found.")
        return False

    plan = get_plan_by_id(plan_id)
    if not plan:
        logger.error(f"_activate_user_plan: Plan {plan_id} not found for user {user_account_number}.")
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
        logger.error(f"_activate_user_plan: Pydantic validation error for UserModify for user {user_account_number}: {e}. Payload: {filtered_payload_dict}", exc_info=True)
        return False

    try:
        updated_user_orm = crud.update_user(db=db, dbuser=db_user_orm, modify=user_modify_payload)

        # If traffic reset is desired upon plan activation (e.g., new data limit applied)
        # and the plan implies it, you might call it here.
        if plan.data_limit is not None: # Or some other condition indicating traffic reset
            logger.info(f"_activate_user_plan: Plan includes data limit, resetting traffic for user {user_account_number}.")
            updated_user_orm = crud.reset_user_data_usage(db=db, dbuser=updated_user_orm) # Returns the updated user

        # Ensure user has all default proxy types
        logger.info(f"_activate_user_plan: Ensuring default proxy types for user {user_account_number}")
        crud.ensure_all_default_proxies_for_user(db=db, user_id=updated_user_orm.id)

        # Refresh the user object to get the updated proxies
        db.refresh(updated_user_orm)
        user_response_for_xray = UserResponse.model_validate(updated_user_orm, context={'db': db})

        background_tasks.add_task(xray.operations.update_user, user_id=updated_user_orm.id)

        logger.info(f"_activate_user_plan: User {user_account_number} processed for plan {plan_id}. Xray update task scheduled.")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"_activate_user_plan: Error updating user {user_account_number} or scheduling Xray: {e}", exc_info=True)
        return False


# --- Route Handlers ---
@router.get("/account", response_model=PortalAccountDetailsResponse)
async def get_account_details(
    request: Request,
    db: Session = Depends(get_db),
    current_user_orm: DBUser = Depends(get_current_user)
):
    """Get comprehensive account details for the authenticated client."""
    # Convert ORM user to Pydantic UserResponse with proper context
    current_user = UserResponse.model_validate(
        current_user_orm,
        context={'db': db, 'request': request}
    )

    # Get active node information if user has one
    active_node = None
    if current_user.active_node_id:
        active_node_orm = crud.get_node_by_id(db, current_user.active_node_id)
        if active_node_orm:
            active_node = NodeResponse.model_validate(active_node_orm)

    # Get all available nodes for activation
    available_nodes_orm = crud.get_nodes(
        db,
        status=NodeStatus.connected,  # Only show connected nodes
        enabled=True  # Only show enabled nodes
    )
    available_nodes = [NodeResponse.model_validate(node) for node in available_nodes_orm]

    return PortalAccountDetailsResponse(
        user=current_user,
        active_node=active_node,
        available_nodes=available_nodes,
        stripe_public_key=STRIPE_PUBLIC_KEY,
        mock_stripe_payment=MOCK_STRIPE_PAYMENT,
        frontend_url=FRONTEND_URL,
        stripe_enabled=bool(STRIPE_PUBLIC_KEY)
    )

@router.get("/servers", response_model=List[NodeResponse])
async def get_servers(
    request: Request,
    db: Session = Depends(get_db),
    current_user_orm: DBUser = Depends(get_current_user)
):
    """Get a list of available servers/nodes for the authenticated client."""
    # Convert ORM user to Pydantic UserResponse with proper context
    current_user = UserResponse.model_validate(
        current_user_orm,
        context={'db': db, 'request': request}
    )

    # Get nodes with appropriate status and enabled flag
    nodes_orm = crud.get_nodes(
        db,
        status=[NodeStatus.connected, NodeStatus.connecting],
        enabled=True
    )

    # Convert ORM nodes to Pydantic NodeResponse models
    nodes = [NodeResponse.model_validate(node) for node in nodes_orm]

    return nodes

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: ClientLoginRequest,
    db: Session = Depends(get_db)
):
    logger.info(f"[LOGIN] Endpoint called with account_number: {login_data.account_number}")
    try:
        logger.debug(f"[LOGIN] Querying user from DB for account_number: {login_data.account_number}")
        user = crud.get_user(db, account_number=login_data.account_number.lower())
        if not user:
            logger.warning(f"[LOGIN] No user found for account_number: {login_data.account_number}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid account number"
            )
        logger.info(f"[LOGIN] User found: {user}")
        logger.debug(f"[LOGIN] User details: account_number={user.account_number}, status={getattr(user, 'status', 'unknown')}, id={getattr(user, 'id', 'unknown')}")
        access_token = create_access_token(data={"sub": user.account_number})
        logger.info(f"[LOGIN] Login successful for account_number: {user.account_number}")
        return TokenResponse(access_token=access_token)
    except Exception as e:
        logger.error(f"[LOGIN] Exception occurred: {e}", exc_info=True)
        raise

@router.post("/register", response_model=TokenResponse)
async def register(
    request: Request,
    db: Session = Depends(get_db)
):
    logger.info("[REGISTER] Endpoint called")
    generated_account_number = str(uuid.uuid4())
    logger.info(f"[REGISTER] Generated account_number: {generated_account_number}")
    default_proxies_for_new_user = {}
    try:
        logger.debug("[REGISTER] Attempting to populate default proxies for new user")
        if hasattr(xray, 'config') and hasattr(xray.config, 'inbounds_by_protocol'):
            for pt_enum_member in ProxyTypes:
                if xray.config.inbounds_by_protocol.get(pt_enum_member.value):
                    settings_model_class = pt_enum_member.settings_model
                    if settings_model_class:
                        default_proxies_for_new_user[pt_enum_member] = settings_model_class()
        logger.debug(f"[REGISTER] Default proxies: {default_proxies_for_new_user}")
    except Exception as e:
        logger.error(f"[REGISTER] Error populating default proxies for {generated_account_number}: {str(e)}", exc_info=True)
    try:
        logger.debug("[REGISTER] Creating UserCreate payload")
        user_payload = UserCreate(
            account_number=generated_account_number,
            proxies=default_proxies_for_new_user,
            status=UserStatusCreate.disabled,
            data_limit=None,
            expire=None,
            data_limit_reset_strategy="no_reset",
            note="Registered via Client Portal",
            on_hold_expire_duration=None,
            on_hold_timeout=None,
            auto_delete_in_days=None,
            next_plan=None
        )
        logger.info(f"[REGISTER] Attempting to create user in DB: account_number={generated_account_number}, status={user_payload.status}")
        new_db_user = crud.create_user(db=db, account_number=generated_account_number, user=user_payload, admin=None)
        logger.info(f"[REGISTER] User created successfully: {new_db_user}")
        logger.debug(f"[REGISTER] User DB object: account_number={new_db_user.account_number}, status={getattr(new_db_user, 'status', 'unknown')}, id={getattr(new_db_user, 'id', 'unknown')}")
        access_token = create_access_token(data={"sub": new_db_user.account_number})
        logger.info(f"[REGISTER] Registration successful, token generated for account_number: {new_db_user.account_number}")
        return TokenResponse(access_token=access_token)
    except Exception as e:
        logger.error(f"[REGISTER] Exception occurred: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
        )

@router.post("/create-checkout-session", name="create_checkout_session")
async def create_checkout_session(
    request: Request,
    plan_id_data: dict,
    db: Session = Depends(get_db),
    current_user_orm: DBUser = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Create a Stripe checkout session for plan purchase."""
    if MOCK_STRIPE_PAYMENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe payments are disabled in mock mode"
        )

    plan_id = plan_id_data.get("plan_id")
    if not plan_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan ID is required"
        )

    plan = get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )

    try:
        checkout_session = stripe.checkout.Sessions.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": plan.name,
                        "description": plan.description
                    },
                    "unit_amount": int(plan.price * 100)  # Convert to cents
                },
                "quantity": 1
            }],
            mode="payment",
            success_url=f"{FRONTEND_URL}/portal/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/portal/checkout/cancel",
            metadata={
                "user_id": current_user_orm.id,
                "plan_id": plan_id
            }
        )
        return {"url": checkout_session.url}
    except Exception as e:
        logger.error(f"Error creating Stripe checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )

@router.post("/stripe-webhook", include_in_schema=False, name="stripe_webhook")
async def stripe_webhook_handler(
    request: Request,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Handle Stripe webhook events."""
    if MOCK_STRIPE_PAYMENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe webhooks are disabled in mock mode"
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature or webhook secret"
        )

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Stripe webhook signature: {str(e)}"
        )

    if event.type == "checkout.session.completed":
        session = event.data.object
        user_id = session.metadata.get("user_id")
        plan_id = session.metadata.get("plan_id")

        if not user_id or not plan_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing user_id or plan_id in session metadata"
            )

        user = crud.get_user_by_id(db, int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        success = await _activate_user_plan(
            db=db,
            user_account_number=user.account_number,
            plan_id=plan_id,
            background_tasks=background_tasks
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to activate plan"
            )

    return {"status": "success"}

@router.post("/account/activate", response_model=UserResponse, name="activate_plan_api")
async def activate_plan_api_endpoint(
    request: Request,
    plan_data: dict,
    db: Session = Depends(get_db),
    current_user_orm: DBUser = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Activate a plan for the authenticated user."""
    if not MOCK_STRIPE_PAYMENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direct plan activation is only available in mock mode"
        )

    plan_id = plan_data.get("plan_id")
    if not plan_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan ID is required"
        )

    success = await _activate_user_plan(
        db=db,
        user_account_number=current_user_orm.account_number,
        plan_id=plan_id,
        background_tasks=background_tasks
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate plan"
        )

    return UserResponse.model_validate(current_user_orm, context={'db': db})

@router.get("/account/plans", response_model=List[PlanResponse])
async def get_available_plans(
    current_user: Optional[DBUser] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Get a list of available plans."""
    plans = crud.get_plans(db)
    return [PlanResponse.model_validate(plan) for plan in plans]

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