from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union
import uuid
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel # Added for NodeActivationRequest

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
from app.models.node import NodeResponse, NodeStatus # Added NodeStatus
from app.models.proxy import ProxyTypes # Removed ShadowsocksSettings as not directly used
from app.utils import report, responses

# Set logging level to DEBUG
logger.setLevel(logging.DEBUG)

router = APIRouter(tags=["User"], prefix="/api", responses={401: responses._401})


class NodeActivationRequest(BaseModel):
    node_id: int


@router.post("/user", response_model=UserResponse, responses={400: responses._400, 409: responses._409})
def add_user(
    new_user: UserCreate,
    # bg: BackgroundTasks, # No background XRay task on simple user creation anymore
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    generated_account_number = new_user.account_number if new_user.account_number else str(uuid.uuid4())
    generated_account_number = generated_account_number.lower()

    # Default proxy configurations logic (remains the same)
    logger.info(f"POST /api/user: Initializing default proxy configurations for new user '{generated_account_number}'.")
    default_proxy_configurations_to_ensure = {}
    if new_user.proxies is None: # Ensure proxies dict exists
        new_user.proxies = {}

    logger.debug(f"Current xray.config.inbounds_by_protocol: {xray.config.inbounds_by_protocol}")
    for pt_enum_member in ProxyTypes:
        logger.debug(f"Checking default proxy for {pt_enum_member.value}")
        if xray.config.inbounds_by_protocol.get(pt_enum_member.value):
            settings_model_class = pt_enum_member.settings_model
            if settings_model_class:
                if pt_enum_member not in new_user.proxies: # Add if not provided
                    logger.debug(f"Protocol '{pt_enum_member.value}' is enabled. Adding its default settings for user '{generated_account_number}'.")
                    default_proxy_configurations_to_ensure[pt_enum_member] = settings_model_class()
            else:
                logger.warning(f"Protocol '{pt_enum_member.value}' is enabled but has no associated settings_model.")
        else:
            logger.info(f"Protocol '{pt_enum_member.value}' is not configured/disabled. Skipping default for '{generated_account_number}'.")

    for proxy_type_enum, default_settings_instance in default_proxy_configurations_to_ensure.items():
        new_user.proxies[proxy_type_enum] = default_settings_instance

    # Protocol Validation (remains the same)
    logger.debug(f"POST /api/user: Validating final proxy set for user '{generated_account_number}'.")
    if new_user.proxies:
        proxies_to_check = list(new_user.proxies.keys())
        for proxy_type_enum_value in proxies_to_check:
            proxy_type_enum = ProxyTypes(proxy_type_enum_value)
            if not xray.config.inbounds_by_protocol.get(proxy_type_enum.value):
                logger.warning(f"POST /api/user: Validation failed for '{generated_account_number}' - Protocol '{proxy_type_enum.value}' is disabled. Raising 400.")
                raise HTTPException(
                    status_code=400,
                    detail=f"Protocol {proxy_type_enum.value} is disabled on your server or has no defined inbounds.",
                )

    logger.info(f"POST /api/user: Fetching admin '{current_admin.username}' for ownership.")
    db_admin_orm = crud.get_admin(db, current_admin.username)
    if not db_admin_orm:
        logger.error(f"POST /api/user: CRITICAL - Admin '{current_admin.username}' NOT FOUND. Raising 403.")
        raise HTTPException(status_code=403, detail="Performing admin not found in database.")

    try:
        logger.info(f"POST /api/user: Calling crud.create_user for '{generated_account_number}'.")
        db_user_orm = crud.create_user(
            db, account_number=generated_account_number, user=new_user, admin=db_admin_orm
        )
        logger.info(f"POST /api/user: crud.create_user successful for '{generated_account_number}', New User ID: {db_user_orm.id}.")
    except IntegrityError:
        logger.error(f"POST /api/user: IntegrityError for '{generated_account_number}'.", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=409, detail="User with this account number or details already exists")
    except Exception as e:
        logger.error(f"POST /api/user: Unexpected error during crud.create_user for '{generated_account_number}': {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="An unexpected error occurred while creating the user.")

    # User is created in DB. No XRay interaction here.
    # Activation on a node will be a separate step.
    user_response = UserResponse.model_validate(db_user_orm)
    report.user_created(
        user=user_response, # Use the Pydantic model for reporting
        user_id=db_user_orm.id, # Pass id if needed by report
        by=current_admin,
        user_admin=db_user_orm.admin # Pass ORM admin if report expects it
    )
    logger.info(f'New user with account number "{db_user_orm.account_number}" added to DB. No XRay activation yet.')
    return user_response


@router.get("/user/{account_number}", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
def get_user(db_user_orm: DBUser = Depends(get_validated_user)):
    return UserResponse.model_validate(db_user_orm)


@router.put("/user/{account_number}", response_model=UserResponse, responses={400: responses._400, 403: responses._403, 404: responses._404})
def modify_user(
    modified_user: UserModify,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    if modified_user.proxies:
        for proxy_type_enum_value in modified_user.proxies: # Iterate keys
            proxy_type_enum = ProxyTypes(proxy_type_enum_value) # Convert to enum
            if not xray.config.inbounds_by_protocol.get(proxy_type_enum.value):
                raise HTTPException(
                    status_code=400,
                    detail=f"Protocol {proxy_type_enum.value} is disabled on your server",
                )

    old_status = db_user_orm.status
    dbuser_updated_orm = crud.update_user(db, db_user_orm, modified_user)
    user_response_for_bg_and_report = UserResponse.model_validate(dbuser_updated_orm)

    # xray.operations.update_user will handle logic based on new status and active_node_id
    bg.add_task(xray.operations.update_user, user_payload=user_response_for_bg_and_report)

    report.user_updated(
        user=user_response_for_bg_and_report,
        user_admin=dbuser_updated_orm.admin,
        by=current_admin
    )
    logger.info(f'User "{dbuser_updated_orm.account_number}" modified.')

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
    return user_response_for_bg_and_report


@router.delete("/user/{account_number}", responses={403: responses._403, 404: responses._404})
def remove_user_endpoint(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    user_account_number = db_user_orm.account_number
    user_admin_orm = db_user_orm.admin
    active_node_id_at_deletion = db_user_orm.active_node_id

    if active_node_id_at_deletion is not None:
        logger.info(f"User '{user_account_number}' is active on node {active_node_id_at_deletion}. Scheduling deactivation from XRay.")
        # deactivate_user_from_active_node handles DB session internally if needed for XRay ops
        bg.add_task(xray.operations.deactivate_user_from_active_node, account_number=user_account_number)
    else:
        logger.info(f"User '{user_account_number}' has no active node. No XRay deactivation needed.")

    crud.remove_user(db, db_user_orm)

    report.user_deleted(
        account_number=user_account_number,
        user_admin=user_admin_orm, # Pass ORM admin for reporting
        by=current_admin
    )
    logger.info(f'User "{user_account_number}" deleted from DB.')
    return {"detail": "User successfully deleted"}


@router.post("/user/{account_number}/node/activate", response_model=UserResponse, responses={403: responses._403, 404: responses._404, 400: responses._400})
def activate_user_node(
    account_number: str,
    activation_request: NodeActivationRequest,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current), # Assuming admins can do this too
):
    # Permission: depends on get_validated_user logic (e.g. admin owns user or is sudo)
    target_db_node = crud.get_node_by_id(db, activation_request.node_id)
    if not target_db_node:
        raise HTTPException(status_code=404, detail=f"Node with id {activation_request.node_id} not found.")

    if target_db_node.status == NodeStatus.disabled:
        raise HTTPException(status_code=400, detail=f"Node {target_db_node.name} is disabled and cannot be activated by user.")

    if db_user_orm.status not in [UserStatus.active, UserStatus.on_hold]:
        raise HTTPException(status_code=400, detail=f"User status is '{db_user_orm.status.value}'. Cannot activate node.")

    logger.info(f"'{current_admin.username}' initiating activation of node {activation_request.node_id} for user '{account_number}'.")

    # The activate_user_on_node is threaded and will handle DB sessions for its XRay ops
    # It will also update user.active_node_id in the DB.
    bg.add_task(xray.operations.activate_user_on_node,
                account_number=db_user_orm.account_number,
                node_id=activation_request.node_id)

    # Return current user state. Client should understand activation is async.
    # A GET /user/{account_number} afterwards would show the new active_node_id once task completes.
    return UserResponse.model_validate(db_user_orm)


@router.post("/user/{account_number}/reset", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
def reset_user_data_usage(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    active_node_id_before_reset = db_user_orm.active_node_id

    dbuser_reset_orm = crud.reset_user_data_usage(db=db, dbuser=db_user_orm)
    user_response_for_bg_and_report = UserResponse.model_validate(dbuser_reset_orm)

    if active_node_id_before_reset is not None:
        if dbuser_reset_orm.status in [UserStatus.active, UserStatus.on_hold]:
            logger.info(f"User {dbuser_reset_orm.account_number} data reset, status {dbuser_reset_orm.status}. Re-activating on node {active_node_id_before_reset}.")
            bg.add_task(xray.operations.activate_user_on_node,
                        account_number=dbuser_reset_orm.account_number,
                        node_id=active_node_id_before_reset)
        else: # Status became inactive
            logger.info(f"User {dbuser_reset_orm.account_number} data reset, status {dbuser_reset_orm.status}. Deactivating from node {active_node_id_before_reset}.")
            bg.add_task(xray.operations.deactivate_user_from_active_node,
                        account_number=dbuser_reset_orm.account_number)

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
    active_node_id_before_revoke = db_user_orm.active_node_id

    dbuser_revoked_orm = crud.revoke_user_sub(db=db, dbuser=db_user_orm) # This changes proxy UUIDs
    user_response_for_bg_and_report = UserResponse.model_validate(dbuser_revoked_orm)

    if active_node_id_before_revoke is not None:
        if dbuser_revoked_orm.status in [UserStatus.active, UserStatus.on_hold]:
            logger.info(f"User {dbuser_revoked_orm.account_number} subscription revoked. Re-activating on node {active_node_id_before_revoke} with new settings.")
            bg.add_task(xray.operations.activate_user_on_node,
                        account_number=dbuser_revoked_orm.account_number,
                        node_id=active_node_id_before_revoke)
        # If status became inactive (unlikely on revoke), update_user would handle deactivation if called.
        # For revoke, usually user remains active but with new credentials, so re-activation on current node is key.

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
    owner: Optional[List[str]] = Query(None, alias="admin"), # List of admin usernames
    status: Optional[UserStatus] = None,
    sort: Optional[str] = None, # Comma-separated string like "created_at,-used_traffic"
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    sort_options_list = []
    if sort:
        for opt_str in sort.strip(",").split(","):
            enum_opt = crud.UsersSortingOptionsEnum.from_string(opt_str.strip())
            if enum_opt:
                sort_options_list.append(enum_opt)
            else:
                raise HTTPException(status_code=400, detail=f'"{opt_str}" is not a valid sort option')

    admin_usernames_to_filter = None
    if current_admin.is_sudo:
        if owner: # Sudo can filter by specific admin usernames passed in "owner" query param
            admin_usernames_to_filter = owner
        # If sudo and owner is None, no admin filter is applied (all users)
    else: # Non-sudo admin sees only their own users
        admin_usernames_to_filter = [current_admin.username]


    users_orm_list, count = crud.get_users(
        db=db,
        offset=offset,
        limit=limit,
        search=search,
        status=status,
        sort=sort_options_list if sort_options_list else None, # Pass list of enums
        admins=admin_usernames_to_filter, # Pass list of admin usernames
        return_with_count=True,
    )
    users_response_list = [UserResponse.model_validate(u_orm) for u_orm in users_orm_list]
    return {"users": users_response_list, "total": count}


@router.post("/users/reset", responses={403: responses._403, 404: responses._404})
def reset_all_users_data_usage( # Renamed to avoid conflict if another function name existed
    bg: BackgroundTasks, # Added background tasks
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.check_sudo_admin)
):
    db_admin_orm_performing_reset = crud.get_admin(db, current_admin.username)
    if not db_admin_orm_performing_reset:
         raise HTTPException(status_code=403, detail="Performing admin not found in database.")

    # Get all users before reset to check their active nodes
    all_users_before_reset = crud.get_users(db=db, admins=None if current_admin.is_sudo else [current_admin.username]) # Get all relevant users

    crud.reset_all_users_data_usage(db=db, admin=None if current_admin.is_sudo else db_admin_orm_performing_reset)

    # After resetting all users, their Xray configs might need updates if their status changed
    # or if reset implies re-application of config.
    # This is a heavy operation. Instead of restarting core, iterate and update if active.
    logger.info("All users' data usage reset. Scheduling XRay updates for affected active users.")
    for user_before_reset in all_users_before_reset:
        if user_before_reset.active_node_id:
            # Re-fetch the user to get post-reset status
            user_after_reset = crud.get_user_by_id(db, user_before_reset.id)
            if user_after_reset: # Should exist
                user_payload_for_xray = UserResponse.model_validate(user_after_reset)
                if user_after_reset.status in [UserStatus.active, UserStatus.on_hold]:
                    logger.debug(f"User {user_after_reset.account_number} active on node {user_after_reset.active_node_id} after global reset. Re-activating.")
                    bg.add_task(xray.operations.activate_user_on_node,
                                account_number=user_after_reset.account_number,
                                node_id=user_after_reset.active_node_id)
                else: # Became inactive
                    logger.debug(f"User {user_after_reset.account_number} inactive after global reset. Deactivating from node {user_before_reset.active_node_id}.")
                    bg.add_task(xray.operations.deactivate_user_from_active_node,
                                account_number=user_after_reset.account_number)

    logger.info(f"All users' data usage reset by admin '{current_admin.username}'. XRay updates scheduled.")
    return {"detail": "All users' data usage successfully reset. XRay updates processing."}


@router.get("/user/{account_number}/usage", response_model=UserUsagesResponse, responses={403: responses._403, 404: responses._404})
def get_user_usage(
    db_user_orm: DBUser = Depends(get_validated_user),
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db),
):
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
    if db_user_orm.next_plan is None:
        raise HTTPException(status_code=404, detail=f"User '{db_user_orm.account_number}' doesn't have a next plan")

    active_node_id_before_next_plan = db_user_orm.active_node_id
    dbuser_reset_orm = crud.reset_user_by_next(db=db, dbuser=db_user_orm)

    user_response_for_bg_and_report = UserResponse.model_validate(dbuser_reset_orm)

    # Activating next plan usually makes user active. If they were on a node, re-activate.
    if active_node_id_before_next_plan is not None:
        if dbuser_reset_orm.status in [UserStatus.active, UserStatus.on_hold]: # Should be active
            logger.info(f"User {dbuser_reset_orm.account_number} activated next plan. Re-activating on node {active_node_id_before_next_plan}.")
            bg.add_task(xray.operations.activate_user_on_node,
                        account_number=dbuser_reset_orm.account_number,
                        node_id=active_node_id_before_next_plan)
        # else: # Unlikely after next_plan activation, but for completeness
            # bg.add_task(xray.operations.deactivate_user_from_active_node, account_number=dbuser_reset_orm.account_number)

    report.user_data_reset_by_next(
        user=user_response_for_bg_and_report,
        user_admin=dbuser_reset_orm.admin,
        by=current_admin
    )
    logger.info(f'User "{dbuser_reset_orm.account_number}"\'s usage was reset by next plan')
    return user_response_for_bg_and_report


@router.get("/users/usage", response_model=UsersUsagesResponse)
def get_all_users_usage_endpoint( # Renamed to avoid conflict
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db),
    owner: Optional[List[str]] = Query(None, alias="admin"), # List of admin usernames
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    start_dt_obj, end_dt_obj = validate_dates(start, end)
    admin_usernames_to_filter = None
    if current_admin.is_sudo:
        if owner: admin_usernames_to_filter = owner
    else:
        admin_usernames_to_filter = [current_admin.username]

    usages = crud.get_all_users_usages(
        db=db, start=start_dt_obj, end=end_dt_obj, admin_usernames=admin_usernames_to_filter
    )
    return {"usages": usages}


@router.put("/user/{account_number}/set-owner", response_model=UserResponse)
def set_owner(
    admin_username_body: str = Query(..., description="Username of the new admin owner"),
    db_user_orm: DBUser = Depends(get_validated_user),
    db: Session = Depends(get_db),
    performing_admin: PydanticAdmin = Depends(PydanticAdmin.check_sudo_admin),
):
    new_admin_orm = crud.get_admin(db, username=admin_username_body)
    if not new_admin_orm:
        raise HTTPException(status_code=404, detail=f"New admin owner '{admin_username_body}' not found")
    if db_user_orm.admin_id == new_admin_orm.id:
        raise HTTPException(status_code=400, detail=f"User is already owned by admin '{admin_username_body}'")

    old_owner_username = db_user_orm.admin.username if db_user_orm.admin else "None"
    dbuser_updated_orm = crud.set_owner(db, db_user_orm, new_admin_orm)
    user_response_for_report = UserResponse.model_validate(dbuser_updated_orm)

    report.user_owner_changed(
        user=user_response_for_report,
        old_owner_username=old_owner_username,
        new_owner_username=new_admin_orm.username,
        by=performing_admin
    )
    logger.info(f'User "{dbuser_updated_orm.account_number}" owner set to "{new_admin_orm.username}" by admin "{performing_admin.username}"')
    return user_response_for_report


@router.get("/users/expired", response_model=List[str])
def get_expired_users_endpoint(
    expired_after: Optional[datetime] = Query(None, description="ISO 8601 format e.g., 2024-01-01T00:00:00Z"),
    expired_before: Optional[datetime] = Query(None, description="ISO 8601 format e.g., 2024-01-31T23:59:59Z"),
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    dt_expired_after, dt_expired_before = validate_dates(
        expired_after.isoformat() if expired_after else None,
        expired_before.isoformat() if expired_before else None
    )
    expired_users_orm_list = get_expired_users_list(db, current_admin, dt_expired_after, dt_expired_before)
    return [u.account_number for u in expired_users_orm_list]


@router.delete("/users/expired", response_model=List[str])
def delete_expired_users_endpoint(
    bg: BackgroundTasks,
    expired_after: Optional[datetime] = Query(None, description="ISO 8601 format e.g., 2024-01-01T00:00:00Z"),
    expired_before: Optional[datetime] = Query(None, description="ISO 8601 format e.g., 2024-01-31T23:59:59Z"),
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    dt_expired_after, dt_expired_before = validate_dates(
        expired_after.isoformat() if expired_after else None,
        expired_before.isoformat() if expired_before else None
    )
    expired_users_orm_list = get_expired_users_list(db, current_admin, dt_expired_after, dt_expired_before)
    if not expired_users_orm_list: return []

    removed_users_accounts = []
    for user_orm in expired_users_orm_list:
        removed_users_accounts.append(user_orm.account_number)
        if user_orm.active_node_id is not None:
            logger.info(f"Expired user '{user_orm.account_number}' active on node {user_orm.active_node_id}. Scheduling deactivation.")
            bg.add_task(xray.operations.deactivate_user_from_active_node, account_number=user_orm.account_number)

        # Reporting info to be captured before deletion if needed by report task
        user_admin_for_report = user_orm.admin # Capture before potential detachment

        # Schedule report task
        bg.add_task(
            report.user_deleted,
            account_number=user_orm.account_number, # Pass account_number
            user_admin=user_admin_for_report, # Pass admin object
            by=current_admin,
        )
        logger.info(f'Expired user "{user_orm.account_number}" scheduled for deletion by admin "{current_admin.username}"')

    if expired_users_orm_list:
        crud.remove_users(db, expired_users_orm_list) # Batch delete from DB after scheduling tasks

    return removed_users_accounts