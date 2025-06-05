from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union
import uuid
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel

from app import xray
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
from app.models.node import NodeResponse, NodeStatus
from app.models.proxy import ProxyTypes
from app.utils import report, responses

# Set logging level to DEBUG
logging.getLogger("marzban").setLevel(logging.DEBUG)

router = APIRouter(tags=["Users"], responses={401: responses._401})


@router.post("", response_model=UserResponse, responses={400: responses._400, 409: responses._409})
def add_user(
    new_user: UserCreate,
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    generated_account_number = new_user.account_number if new_user.account_number else str(uuid.uuid4())
    generated_account_number = generated_account_number.lower()

    # Default proxy configurations logic
    logging.getLogger("marzban").info(f"POST /api/admin/users: Initializing default proxy configurations for new user '{generated_account_number}'.")
    default_proxy_configurations_to_ensure = {}
    if new_user.proxies is None:
        new_user.proxies = {}

    logging.getLogger("marzban").debug(f"Current xray.config.inbounds_by_protocol: {xray.config.inbounds_by_protocol}")
    for pt_enum_member in ProxyTypes:
        logging.getLogger("marzban").debug(f"Checking default proxy for {pt_enum_member.value}")
        if xray.config.inbounds_by_protocol.get(pt_enum_member.value):
            settings_model_class = pt_enum_member.settings_model
            if settings_model_class:
                if pt_enum_member not in new_user.proxies:
                    logging.getLogger("marzban").debug(f"Protocol '{pt_enum_member.value}' is enabled. Adding its default settings for user '{generated_account_number}'.")
                    default_proxy_configurations_to_ensure[pt_enum_member] = settings_model_class()
            else:
                logging.getLogger("marzban").warning(f"Protocol '{pt_enum_member.value}' is enabled but has no associated settings_model.")
        else:
            logging.getLogger("marzban").info(f"Protocol '{pt_enum_member.value}' is not configured/disabled. Skipping default for '{generated_account_number}'.")

    for proxy_type_enum, default_settings_instance in default_proxy_configurations_to_ensure.items():
        new_user.proxies[proxy_type_enum] = default_settings_instance

    # Protocol Validation
    logging.getLogger("marzban").debug(f"POST /api/admin/users: Validating final proxy set for user '{generated_account_number}'.")
    if new_user.proxies:
        proxies_to_check = list(new_user.proxies.keys())
        for proxy_type_enum_value in proxies_to_check:
            proxy_type_enum = ProxyTypes(proxy_type_enum_value)
            if not xray.config.inbounds_by_protocol.get(proxy_type_enum.value):
                logging.getLogger("marzban").warning(f"POST /api/admin/users: Validation failed for '{generated_account_number}' - Protocol '{proxy_type_enum.value}' is disabled. Raising 400.")
                raise HTTPException(
                    status_code=400,
                    detail=f"Protocol {proxy_type_enum.value} is disabled on your server or has no defined inbounds.",
                )

    logging.getLogger("marzban").info(f"POST /api/admin/users: Fetching admin '{current_admin.username}' for ownership.")
    db_admin_orm = crud.get_admin(db, current_admin.username)
    if not db_admin_orm:
        logging.getLogger("marzban").error(f"POST /api/admin/users: CRITICAL - Admin '{current_admin.username}' NOT FOUND. Raising 403.")
        raise HTTPException(status_code=403, detail="Performing admin not found in database.")

    try:
        logging.getLogger("marzban").info(f"POST /api/admin/users: Calling crud.create_user for '{generated_account_number}'.")
        db_user_orm = crud.create_user(
            db, account_number=generated_account_number, user=new_user, admin=db_admin_orm
        )
        logging.getLogger("marzban").info(f"POST /api/admin/users: crud.create_user successful for '{generated_account_number}', New User ID: {db_user_orm.id}.")
    except IntegrityError:
        logging.getLogger("marzban").error(f"POST /api/admin/users: IntegrityError for '{generated_account_number}'.", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=409, detail="User with this account number or details already exists")
    except Exception as e:
        logging.getLogger("marzban").error(f"POST /api/admin/users: Unexpected error during crud.create_user for '{generated_account_number}': {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="An unexpected error occurred while creating the user.")

    user_response = UserResponse.model_validate(db_user_orm, context={'db': db})
    report.user_created(
        user=user_response,
        user_id=db_user_orm.id,
        by=current_admin,
        user_admin=db_user_orm.admin
    )
    logging.getLogger("marzban").info(f'New user with account number "{db_user_orm.account_number}" added to DB. No XRay activation yet.')
    return user_response


@router.get("/{account_number}", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
def get_user(db_user_orm: DBUser = Depends(get_validated_user), db: Session = Depends(get_db)):
    return UserResponse.model_validate(db_user_orm, context={'db': db})


@router.put("/{account_number}", response_model=UserResponse, responses={400: responses._400, 403: responses._403, 404: responses._404})
def modify_user(
    modified_user: UserModify,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    if modified_user.proxies:
        for proxy_type_enum_value in modified_user.proxies:
            proxy_type_enum = ProxyTypes(proxy_type_enum_value)
            if not xray.config.inbounds_by_protocol.get(proxy_type_enum.value):
                raise HTTPException(
                    status_code=400,
                    detail=f"Protocol {proxy_type_enum.value} is disabled on your server",
                )

    old_status = db_user_orm.status
    dbuser_updated_orm = crud.update_user(db, db_user_orm, modified_user)
    user_response_for_bg_and_report = UserResponse.model_validate(dbuser_updated_orm, context={'db': db})

    bg.add_task(xray.operations.update_user, user_id=dbuser_updated_orm.id)

    report.user_updated(
        user=user_response_for_bg_and_report,
        user_admin=dbuser_updated_orm.admin,
        by=current_admin
    )
    logging.getLogger("marzban").info(f'User "{dbuser_updated_orm.account_number}" modified.')

    if dbuser_updated_orm.status != old_status:
        report.status_change(
            account_number=dbuser_updated_orm.account_number,
            status=dbuser_updated_orm.status,
            user=user_response_for_bg_and_report,
            user_admin=dbuser_updated_orm.admin,
            by=current_admin,
        )
        logging.getLogger("marzban").info(
            f'User "{dbuser_updated_orm.account_number}" status changed from {old_status.value} to {dbuser_updated_orm.status.value}'
        )
    return user_response_for_bg_and_report


@router.delete("/{account_number}", responses={403: responses._403, 404: responses._404})
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
        logging.getLogger("marzban").info(f"User '{user_account_number}' is active on node {active_node_id_at_deletion}. Scheduling deactivation from XRay.")
        bg.add_task(xray.operations.deactivate_user_from_active_node, account_number=user_account_number)
    else:
        logging.getLogger("marzban").info(f"User '{user_account_number}' has no active node. No XRay deactivation needed.")

    crud.remove_user(db, db_user_orm)

    report.user_deleted(
        account_number=user_account_number,
        user_admin=user_admin_orm,
        by=current_admin
    )
    logging.getLogger("marzban").info(f'User "{user_account_number}" deleted from DB.')
    return {"detail": "User successfully deleted"}


@router.post("/{account_number}/reset", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
def reset_user_data_usage(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    active_node_id_before_reset = db_user_orm.active_node_id

    dbuser_reset_orm = crud.reset_user_data_usage(db=db, dbuser=db_user_orm)
    user_response_for_bg_and_report = UserResponse.model_validate(dbuser_reset_orm, context={'db': db})

    if active_node_id_before_reset is not None:
        if dbuser_reset_orm.status in [UserStatus.active, UserStatus.on_hold]:
            logging.getLogger("marzban").info(f"User {dbuser_reset_orm.account_number} data reset, status {dbuser_reset_orm.status}. Re-activating on node {active_node_id_before_reset}.")
            bg.add_task(xray.operations.activate_user_on_node,
                        account_number=dbuser_reset_orm.account_number,
                        node_id=active_node_id_before_reset)
        else:
            logging.getLogger("marzban").info(f"User {dbuser_reset_orm.account_number} data reset, status {dbuser_reset_orm.status}. Deactivating from node {active_node_id_before_reset}.")
            bg.add_task(xray.operations.deactivate_user_from_active_node,
                        account_number=dbuser_reset_orm.account_number)

    report.user_data_usage_reset(
        user=user_response_for_bg_and_report,
        user_admin=dbuser_reset_orm.admin,
        by=current_admin
    )
    logging.getLogger("marzban").info(f'User "{dbuser_reset_orm.account_number}"\'s usage was reset')
    return user_response_for_bg_and_report


@router.post("/{account_number}/revoke_sub", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
def revoke_user_subscription(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    active_node_id_before_revoke = db_user_orm.active_node_id

    dbuser_revoked_orm = crud.revoke_user_sub(db=db, dbuser=db_user_orm)
    user_response_for_bg_and_report = UserResponse.model_validate(dbuser_revoked_orm, context={'db': db})

    if active_node_id_before_revoke is not None:
        if dbuser_revoked_orm.status in [UserStatus.active, UserStatus.on_hold]:
            logging.getLogger("marzban").info(f"User {dbuser_revoked_orm.account_number} subscription revoked. Re-activating on node {active_node_id_before_revoke} with new settings.")
            bg.add_task(xray.operations.activate_user_on_node,
                        account_number=dbuser_revoked_orm.account_number,
                        node_id=active_node_id_before_revoke)

    report.user_subscription_revoked(
        user=user_response_for_bg_and_report,
        user_admin=dbuser_revoked_orm.admin,
        by=current_admin
    )
    logging.getLogger("marzban").info(f'User "{dbuser_revoked_orm.account_number}" subscription revoked')
    return user_response_for_bg_and_report


@router.get("", response_model=UsersResponse, responses={400: responses._400, 403: responses._403, 404: responses._404})
def get_users(
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    search: Optional[str] = None,
    status: Optional[UserStatus] = None,
    sort: Optional[str] = None,
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

    users_orm_list, count = crud.get_users(
        db=db,
        offset=offset,
        limit=limit,
        search=search,
        status=status,
        sort=sort_options_list if sort_options_list else None,
        return_with_count=True,
    )
    users_response_list = [UserResponse.model_validate(u_orm, context={'db': db}) for u_orm in users_orm_list]
    return {"users": users_response_list, "total": count}


@router.post("/reset", responses={403: responses._403, 404: responses._404})
def reset_all_users_data_usage(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.check_sudo_admin)
):
    db_admin_orm_performing_reset = crud.get_admin(db, current_admin.username)
    if not db_admin_orm_performing_reset:
         raise HTTPException(status_code=403, detail="Performing admin not found in database.")

    all_users_before_reset = crud.get_users(db=db, admins=None if current_admin.is_sudo else [current_admin.username])

    crud.reset_all_users_data_usage(db=db, admin=None if current_admin.is_sudo else db_admin_orm_performing_reset)

    logging.getLogger("marzban").info("All users' data usage reset. Scheduling XRay updates for affected active users.")
    for user_before_reset in all_users_before_reset:
        if user_before_reset.active_node_id:
            user_after_reset = crud.get_user_by_id(db, user_before_reset.id)
            if user_after_reset:
                user_payload_for_xray = UserResponse.model_validate(user_after_reset, context={'db': db})
                if user_after_reset.status in [UserStatus.active, UserStatus.on_hold]:
                    logging.getLogger("marzban").debug(f"User {user_after_reset.account_number} active on node {user_after_reset.active_node_id} after global reset. Re-activating.")
                    bg.add_task(xray.operations.activate_user_on_node,
                                account_number=user_after_reset.account_number,
                                node_id=user_after_reset.active_node_id)
                else:
                    logging.getLogger("marzban").debug(f"User {user_after_reset.account_number} inactive after global reset. Deactivating from node {user_before_reset.active_node_id}.")
                    bg.add_task(xray.operations.deactivate_user_from_active_node,
                                account_number=user_after_reset.account_number)

    logging.getLogger("marzban").info(f"All users' data usage reset by admin '{current_admin.username}'. XRay updates scheduled.")
    return {"detail": "All users' data usage successfully reset. XRay updates processing."}


@router.get("/{account_number}/usage", response_model=UserUsagesResponse, responses={403: responses._403, 404: responses._404})
def get_user_usage(
    db_user_orm: DBUser = Depends(get_validated_user),
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db),
):
    start_dt_obj, end_dt_obj = validate_dates(start, end)
    usages = crud.get_user_usages(db, db_user_orm, start_dt_obj, end_dt_obj)
    return {"usages": usages, "account_number": db_user_orm.account_number}


@router.post("/{account_number}/active-next", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
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

    user_response_for_bg_and_report = UserResponse.model_validate(dbuser_reset_orm, context={'db': db})

    if active_node_id_before_next_plan is not None:
        if dbuser_reset_orm.status in [UserStatus.active, UserStatus.on_hold]:
            logging.getLogger("marzban").info(f"User {dbuser_reset_orm.account_number} activated next plan. Re-activating on node {active_node_id_before_next_plan}.")
            bg.add_task(xray.operations.activate_user_on_node,
                        account_number=dbuser_reset_orm.account_number,
                        node_id=active_node_id_before_next_plan)

    report.user_data_reset_by_next(
        user=user_response_for_bg_and_report,
        user_admin=dbuser_reset_orm.admin,
        by=current_admin
    )
    logging.getLogger("marzban").info(f'User "{dbuser_reset_orm.account_number}"\'s usage was reset by next plan')
    return user_response_for_bg_and_report


@router.get("/usage", response_model=UsersUsagesResponse)
def get_all_users_usage_endpoint(
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    start_dt_obj, end_dt_obj = validate_dates(start, end)
    usages = crud.get_all_users_usages(
        db=db, start=start_dt_obj, end=end_dt_obj
    )
    return {"usages": usages}


@router.get("/expired", response_model=List[str])
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


@router.delete("/expired", response_model=List[str])
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
            logging.getLogger("marzban").info(f"Expired user '{user_orm.account_number}' active on node {user_orm.active_node_id}. Scheduling deactivation.")
            bg.add_task(xray.operations.deactivate_user_from_active_node, account_number=user_orm.account_number)

        user_admin_for_report = user_orm.admin

        bg.add_task(
            report.user_deleted,
            account_number=user_orm.account_number,
            user_admin=user_admin_for_report,
            by=current_admin,
        )
        logging.getLogger("marzban").info(f'Expired user "{user_orm.account_number}" scheduled for deletion by admin "{current_admin.username}"')

    if expired_users_orm_list:
        crud.remove_users(db, expired_users_orm_list)

    return removed_users_accounts