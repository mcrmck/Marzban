from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError

from app import logger, xray
from app.db import Session, crud, get_db
from app.db.models import User as DBUser
from app.db.models import Admin as DBAdmin
from app.dependencies import get_expired_users_list, get_validated_user, validate_dates
from app.models.admin import Admin as PydanticAdmin
from app.models.user import (
    UserCreate,
    UserModify,
    UserResponse,
    UsersResponse,
    UserStatus,
    UserUsagesResponse,
    UsersUsagesResponse,
)
from app.models.node import NodeResponse
from app.models.proxy import ProxyTypes, ShadowsocksSettings
from app.utils import report, responses

router = APIRouter(tags=["User"], prefix="/api", responses={401: responses._401})


@router.post("/user", response_model=UserResponse, responses={400: responses._400, 409: responses._409})
def add_user(
    new_user: UserCreate,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    # ... (generated_account_number logic remains the same) ...
    generated_account_number = new_user.account_number if new_user.account_number else str(uuid.uuid4())
    generated_account_number = generated_account_number.lower()

    # --- START: Modified Logic to add default proxy types ---
    logger.info(f"POST /api/user: Initializing default proxy configurations for new user '{generated_account_number}'.")
    default_proxy_configurations_to_ensure = {}

    for pt_enum_member in ProxyTypes: # Iterate through all defined ProxyTypes
        # IMPORTANT: Only consider adding a default if the protocol is actually enabled on the server
        if xray.config.inbounds_by_protocol.get(pt_enum_member.value):
            settings_model_class = pt_enum_member.settings_model
            if settings_model_class:
                logger.debug(f"Protocol '{pt_enum_member.value}' is enabled. Adding its default settings for user '{generated_account_number}'.")
                default_proxy_configurations_to_ensure[pt_enum_member] = settings_model_class()
            else:
                logger.warning(f"Protocol '{pt_enum_member.value}' is enabled but has no associated settings_model in app/models/proxy.py.")
        else:
            logger.info(f"Protocol '{pt_enum_member.value}' is not configured or disabled on the server. Skipping for default user provision for '{generated_account_number}'.")

    if new_user.proxies is None:
        new_user.proxies = {}

    # Apply defaults only if the proxy type wasn't in the original request from the client
    for proxy_type_enum, default_settings_instance in default_proxy_configurations_to_ensure.items():
        if proxy_type_enum not in new_user.proxies:
            logger.debug(f"Adding default '{proxy_type_enum.value}' proxy settings to user '{generated_account_number}' as it was not in the request.")
            new_user.proxies[proxy_type_enum] = default_settings_instance
        else:
            logger.debug(f"User '{generated_account_number}' request already included settings for '{proxy_type_enum.value}'. Using provided settings.")
    # --- END: Modified Logic to add default proxy types ---

    # --- Protocol Validation (can be kept as a safeguard) ---
    logger.debug(f"POST /api/user: Validating final proxy set for user '{generated_account_number}': { {pt.value: ps.model_dump(exclude_none=True) for pt, ps in new_user.proxies.items()} }")
    proxies_to_check = list(new_user.proxies.keys()) # Make a list of keys before iteration if modifying the dict
    for proxy_type_enum_value in proxies_to_check:
        proxy_type_enum = ProxyTypes(proxy_type_enum_value) # Ensure it's an enum member
        if not xray.config.inbounds_by_protocol.get(proxy_type_enum.value):
            # This should ideally not be hit if frontend only sends enabled ones and above logic is correct
            logger.warning(f"POST /api/user: Validation failed for user '{generated_account_number}' - Protocol '{proxy_type_enum.value}' is present in final user proxy data but is disabled or has no inbounds. Raising 400.")
            raise HTTPException(
                status_code=400,
                detail=f"Protocol {proxy_type_enum.value} is disabled on your server or has no defined inbounds. Cannot assign to user.",
            )

    # ... (rest of the function: fetching db_admin_orm, crud.create_user, etc.) ...
    # Ensure db_admin_orm fetching and subsequent operations are correct as previously discussed
    # Log 4: Before fetching admin from DB for ownership - Enhanced
    logger.info(
        f"POST /api/user: Preparing to fetch admin for ownership. "
        f"Username from Pydantic model current_admin.username: '{current_admin.username}' (repr: {repr(current_admin.username)}). "
        f"Session ID: {id(db)}, Session is active: {db.is_active}, Session dirty: {len(db.dirty)}, Session new: {len(db.new)}"
    )
    db_admin_orm = crud.get_admin(db, current_admin.username) # This is where it fails

    if not db_admin_orm:
        # Log 5: If admin performing the action is not found in DB (critical for the explicit 403) - Enhanced
        logger.error(
            f"POST /api/user: CRITICAL - Admin '{current_admin.username}' (repr: {repr(current_admin.username)}) "
            f"NOT FOUND in DB when called from add_user. "
            f"Session ID: {id(db)}, Session active: {db.is_active}. Raising 403."
        )
        raise HTTPException(status_code=403, detail="Performing admin not found in database.")

    # Log 6: Admin successfully fetched (this part is currently not being reached)
    logger.info(f"POST /api/user: Admin '{current_admin.username}' (ID: {db_admin_orm.id}) successfully fetched from DB for ownership.")
    try:
        logger.info(f"POST /api/user: Calling crud.create_user for account_number: '{generated_account_number}'.")
        db_user_orm = crud.create_user(
            db, account_number=generated_account_number, user=new_user, admin=db_admin_orm
        )
        logger.info(f"POST /api/user: crud.create_user successful for user '{generated_account_number}', New User ID: {db_user_orm.id}.")
    except IntegrityError:
        logger.error(f"POST /api/user: IntegrityError for user '{generated_account_number}'. User might already exist.", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=409, detail="User with this account number or details already exists")
    except Exception as e:
        logger.error(f"POST /api/user: Unexpected error during crud.create_user for user '{generated_account_number}': {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="An unexpected error occurred while creating the user.")

    user_response_for_bg = UserResponse.model_validate(db_user_orm)
    bg.add_task(xray.operations.add_user, user_payload=user_response_for_bg)

    report.user_created(
        user=user_response_for_bg,
        user_id=db_user_orm.id,
        by=current_admin,
        user_admin=db_user_orm.admin
    )
    logger.info(f'New user with account number "{db_user_orm.account_number}" added.')
    return user_response_for_bg


@router.get("/user/{account_number}", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
def get_user(db_user_orm: DBUser = Depends(get_validated_user)):
    """Get user information by account number"""
    # get_validated_user uses crud.get_user, which uses get_user_queryset (eager loading)
    return UserResponse.model_validate(db_user_orm)


@router.put("/user/{account_number}", response_model=UserResponse, responses={400: responses._400, 403: responses._403, 404: responses._404})
def modify_user(
    modified_user: UserModify,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user), # This is pre-update ORM user
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """
    Modify an existing user.
    """
    if modified_user.proxies:
        for proxy_type_enum in modified_user.proxies:
            if not xray.config.inbounds_by_protocol.get(proxy_type_enum.value):
                raise HTTPException(
                    status_code=400,
                    detail=f"Protocol {proxy_type_enum.value} is disabled on your server",
                )

    old_status = db_user_orm.status
    # crud.update_user returns the updated ORM user, ideally with relations reloaded/refreshed
    dbuser_updated_orm = crud.update_user(db, db_user_orm, modified_user)

    # Convert updated ORM model to Pydantic UserResponse for Xray operations and reporting
    user_response_for_bg_and_report = UserResponse.model_validate(dbuser_updated_orm)

    if dbuser_updated_orm.status in [UserStatus.active, UserStatus.on_hold]:
        bg.add_task(xray.operations.update_user, user_payload=user_response_for_bg_and_report)
    else: # User is disabled, limited, expired - remove from Xray
        bg.add_task(xray.operations.remove_user, account_number=dbuser_updated_orm.account_number)

    report.user_updated(
        user=user_response_for_bg_and_report,
        user_admin=dbuser_updated_orm.admin,
        by=current_admin
    )
    logger.info(f'User "{dbuser_updated_orm.account_number}" modified')

    if dbuser_updated_orm.status != old_status:
        report.status_change(
            account_number=dbuser_updated_orm.account_number,
            status=dbuser_updated_orm.status,
            user=user_response_for_bg_and_report,
            user_admin=dbuser_updated_orm.admin,
            by=current_admin,
        )
        logger.info(
            f'User "{dbuser_updated_orm.account_number}" status changed from {old_status.value} to {dbuser_updated_orm.status.value}'
        )
    return user_response_for_bg_and_report # Return Pydantic model


@router.delete("/user/{account_number}", responses={403: responses._403, 404: responses._404})
def remove_user_endpoint( # Renamed function to avoid conflict with xray.operations.remove_user
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Remove a user by account number"""
    user_account_number = db_user_orm.account_number
    user_admin_orm = db_user_orm.admin

    # Schedule Xray removal before DB deletion, passing the account number
    bg.add_task(xray.operations.remove_user, account_number=user_account_number)

    crud.remove_user(db, db_user_orm) # Now delete from DB

    report.user_deleted(
        account_number=user_account_number,
        user_admin=user_admin_orm,
        by=current_admin
    )
    logger.info(f'User "{user_account_number}" deleted')
    return {"detail": "User successfully deleted"}


@router.post("/user/{account_number}/reset", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
def reset_user_data_usage(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Reset user data usage by account number"""
    dbuser_reset_orm = crud.reset_user_data_usage(db=db, dbuser=db_user_orm)
    user_response_for_bg_and_report = UserResponse.model_validate(dbuser_reset_orm)

    if dbuser_reset_orm.status in [UserStatus.active, UserStatus.on_hold]:
        # After reset, user config might need to be re-added/updated in Xray
        # add_user operation in Xray usually handles creating or overwriting.
        bg.add_task(xray.operations.add_user, user_payload=user_response_for_bg_and_report)
    else: # If reset made user inactive (e.g. if status logic changes)
        bg.add_task(xray.operations.remove_user, account_number=dbuser_reset_orm.account_number)


    report.user_data_usage_reset(
        user=user_response_for_bg_and_report,
        user_admin=dbuser_reset_orm.admin,
        by=current_admin
    )
    logger.info(f'User "{dbuser_reset_orm.account_number}"\'s usage was reset')
    return user_response_for_bg_and_report


@router.post("/user/{account_number}/revoke_sub", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
def revoke_user_subscription(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Revoke user's subscription by account number"""
    dbuser_revoked_orm = crud.revoke_user_sub(db=db, dbuser=db_user_orm)
    user_response_for_bg_and_report = UserResponse.model_validate(dbuser_revoked_orm)

    # Revoking subscription implies user settings (like UUIDs in proxies) change.
    # So, Xray needs an update.
    if dbuser_revoked_orm.status in [UserStatus.active, UserStatus.on_hold]:
        bg.add_task(xray.operations.update_user, user_payload=user_response_for_bg_and_report)
    else: # If revoking makes user inactive
        bg.add_task(xray.operations.remove_user, account_number=dbuser_revoked_orm.account_number)

    report.user_subscription_revoked(
        user=user_response_for_bg_and_report,
        user_admin=dbuser_revoked_orm.admin,
        by=current_admin
    )
    logger.info(f'User "{dbuser_revoked_orm.account_number}" subscription revoked')
    return user_response_for_bg_and_report


@router.get("/users", response_model=UsersResponse, responses={400: responses._400, 403: responses._403, 404: responses._404})
def get_users(
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    search: Optional[str] = None,
    owner: Optional[List[str]] = Query(None, alias="admin"),
    status: Optional[UserStatus] = None,
    sort: Optional[str] = None,
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Get all users"""
    sort_options_enum_list = []
    if sort is not None:
        opts = sort.strip(",").split(",")
        for opt in opts:
            try:
                sort_options_enum_list.append(crud.UsersSortingOptions[opt])
            except KeyError:
                raise HTTPException(
                    status_code=400, detail=f'"{opt}" is not a valid sort option'
                )
    else:
        sort_options_enum_list = None

    admin_usernames_filter = owner if current_admin.is_sudo and owner is not None else [current_admin.username]
    if current_admin.is_sudo and owner is None:
        admin_usernames_filter = None

    users_orm_list, count = crud.get_users(
        db=db,
        offset=offset,
        limit=limit,
        search=search,
        status=status,
        sort=sort_options_enum_list,
        admins=admin_usernames_filter, # Pass list of admin usernames
        return_with_count=True,
    )
    # Convert list of ORM users to list of Pydantic UserResponse models
    users_response_list = [UserResponse.model_validate(u_orm) for u_orm in users_orm_list]
    return {"users": users_response_list, "total": count}


@router.post("/users/reset", responses={403: responses._403, 404: responses._404})
def reset_users_data_usage( # Function name is duplicated, consider renaming for clarity if this is different
    db: Session = Depends(get_db), current_admin: PydanticAdmin = Depends(PydanticAdmin.check_sudo_admin)
):
    """Reset all users data usage (sudo admin only)"""
    db_admin_orm = crud.get_admin(db, current_admin.username)
    if not db_admin_orm: # Should be caught by check_sudo_admin or ensure admin exists
         raise HTTPException(status_code=403, detail="Performing admin not found in database.")

    crud.reset_all_users_data_usage(db=db, admin=None if current_admin.is_sudo else db_admin_orm)

    # After resetting all users, their Xray configs might need updates.
    # This is a heavy operation. A full restart/reconfig of Xray might be needed,
    # or iterate all affected users and call xray.operations.add_user (or update_user).
    # The current approach of restarting Xray core and nodes is one way.
    try:
        logger.info("Resetting all users usage: Triggering Xray core and node reconfigurations.")
        startup_config = xray.config.include_db_users()
        xray.core.restart(startup_config)
        for node_id, node_obj in list(xray.nodes.items()): # Use node_obj for clarity
            if hasattr(node_obj, 'connected') and node_obj.connected and hasattr(node_obj, 'started') and node_obj.started :
                xray.operations.restart_node(node_id, startup_config) # Pass node_id
    except Exception as e:
        logger.error(f"Error during Xray restart/reconfig after resetting all users usage: {e}")

    logger.info(f"All users' data usage reset by admin '{current_admin.username}'")
    return {"detail": "All users' data usage successfully reset."}


@router.get("/user/{account_number}/usage", response_model=UserUsagesResponse, responses={403: responses._403, 404: responses._404})
def get_user_usage(
    db_user_orm: DBUser = Depends(get_validated_user),
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db),
):
    """Get user's usage by account number"""
    start_dt_obj, end_dt_obj = validate_dates(start, end)

    usages = crud.get_user_usages(db, db_user_orm, start_dt_obj, end_dt_obj)
    return {"usages": usages, "account_number": db_user_orm.account_number}


@router.post("/user/{account_number}/active-next", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
def active_next_plan(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Reset user by next plan, identified by account number"""
    if db_user_orm.next_plan is None:
        raise HTTPException(
            status_code=404,
            detail=f"User with account number '{db_user_orm.account_number}' doesn't have a next plan",
        )

    dbuser_reset_orm = crud.reset_user_by_next(db=db, dbuser=db_user_orm)
    if dbuser_reset_orm is None:
         raise HTTPException(status_code=500, detail="Failed to reset user by next plan")

    user_response_for_bg_and_report = UserResponse.model_validate(dbuser_reset_orm)

    if dbuser_reset_orm.status in [UserStatus.active, UserStatus.on_hold]:
        # User's plan changed, so their Xray config (especially if limits/expiry affect it) needs update.
        # add_user will effectively update them if they exist.
        bg.add_task(xray.operations.add_user, user_payload=user_response_for_bg_and_report)

    report.user_data_reset_by_next(
        user=user_response_for_bg_and_report,
        user_admin=dbuser_reset_orm.admin,
        by=current_admin
    )
    logger.info(f'User "{dbuser_reset_orm.account_number}"\'s usage was reset by next plan')
    return user_response_for_bg_and_report


@router.get("/users/usage", response_model=UsersUsagesResponse)
def get_users_usage( # Function name is duplicated, consider renaming for clarity if this is different
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db),
    owner: Optional[List[str]] = Query(None, alias="admin"),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Get all users usage"""
    start_dt_obj, end_dt_obj = validate_dates(start, end)

    admin_usernames_filter = owner if current_admin.is_sudo and owner is not None else [current_admin.username]
    if current_admin.is_sudo and owner is None:
        admin_usernames_filter = None

    # crud.get_all_users_usages expects a list of admin usernames, not an ORM Admin object
    usages = crud.get_all_users_usages(
        db=db, start=start_dt_obj, end=end_dt_obj, admin_usernames=admin_usernames_filter
    )
    return {"usages": usages}


@router.put("/user/{account_number}/set-owner", response_model=UserResponse)
def set_owner(
    admin_username_body: str = Query(..., description="Username of the new admin owner"),
    db_user_orm: DBUser = Depends(get_validated_user),
    db: Session = Depends(get_db),
    performing_admin: PydanticAdmin = Depends(PydanticAdmin.check_sudo_admin),
):
    """Set a new owner (admin) for a user, identified by account number (Sudo admin only)."""
    new_admin_orm = crud.get_admin(db, username=admin_username_body)
    if not new_admin_orm:
        raise HTTPException(status_code=404, detail=f"New admin owner '{admin_username_body}' not found")

    if db_user_orm.admin_id == new_admin_orm.id:
        raise HTTPException(status_code=400, detail=f"User is already owned by admin '{admin_username_body}'")

    old_owner_username_for_report = db_user_orm.admin.username if db_user_orm.admin else "None"

    dbuser_updated_orm = crud.set_owner(db, db_user_orm, new_admin_orm)
    user_response_for_report = UserResponse.model_validate(dbuser_updated_orm)

    report.user_owner_changed(
        user=user_response_for_report,
        old_owner_username=old_owner_username_for_report,
        new_owner_username=new_admin_orm.username,
        by=performing_admin
    )
    logger.info(f'User "{dbuser_updated_orm.account_number}" owner successfully set to "{new_admin_orm.username}" by admin "{performing_admin.username}"')
    return user_response_for_report


@router.get("/users/expired", response_model=List[str])
def get_expired_users_endpoint( # Renamed to avoid conflict
    expired_after: Optional[datetime] = Query(None, description="ISO 8601 format e.g., 2024-01-01T00:00:00"),
    expired_before: Optional[datetime] = Query(None, description="ISO 8601 format e.g., 2024-01-31T23:59:59"),
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Get account numbers of users who have expired within the specified date range."""
    dt_expired_after_obj, dt_expired_before_obj = validate_dates(
        expired_after.isoformat() if expired_after else None,
        expired_before.isoformat() if expired_before else None
    )

    expired_users_orm_list = get_expired_users_list(db, current_admin, dt_expired_after_obj, dt_expired_before_obj)
    return [u.account_number for u in expired_users_orm_list]


@router.delete("/users/expired", response_model=List[str])
def delete_expired_users_endpoint( # Renamed to avoid conflict
    bg: BackgroundTasks,
    expired_after: Optional[datetime] = Query(None, description="ISO 8601 format e.g., 2024-01-01T00:00:00"),
    expired_before: Optional[datetime] = Query(None, description="ISO 8601 format e.g., 2024-01-31T23:59:59"),
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Delete users who have expired within the specified date range. Returns their account numbers."""
    dt_expired_after_obj, dt_expired_before_obj = validate_dates(
        expired_after.isoformat() if expired_after else None,
        expired_before.isoformat() if expired_before else None
    )

    expired_users_orm_list = get_expired_users_list(db, current_admin, dt_expired_after_obj, dt_expired_before_obj)

    if not expired_users_orm_list:
        return []

    removed_users_account_numbers = []
    users_data_for_reporting_and_xray = []

    for user_orm in expired_users_orm_list:
        removed_users_account_numbers.append(user_orm.account_number)
        users_data_for_reporting_and_xray.append({
            "account_number": user_orm.account_number,
            "admin_orm": user_orm.admin # Keep ORM admin for report
        })
        # Schedule Xray removal before DB deletion using account_number
        bg.add_task(xray.operations.remove_user, account_number=user_orm.account_number)

    if expired_users_orm_list: # Ensure there are users to remove
        crud.remove_users(db, expired_users_orm_list) # Batch delete from DB

    for user_data in users_data_for_reporting_and_xray:
        logger.info(f'Expired user with account number "{user_data["account_number"]}" deleted by admin "{current_admin.username}"')
        bg.add_task(
            report.user_deleted,
            account_number=user_data["account_number"],
            user_admin=user_data["admin_orm"],
            by=current_admin,
        )
    return removed_users_account_numbers

