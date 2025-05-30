from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError

from app import logger, xray
from app.db import Session, crud, get_db
from app.db.models import User as DBUser  # Import the ORM User model
from app.db.models import Admin as DBAdmin # Import the ORM Admin model, if needed for type hints
from app.dependencies import get_expired_users_list, get_validated_user, validate_dates
from app.models.admin import Admin as PydanticAdmin # Pydantic Admin model for request/response
from app.models.user import (
    UserCreate,
    UserModify,
    UserResponse,
    UsersResponse,
    UserStatus,
    UsersUsagesResponse,
    UserUsagesResponse,
)
from app.models.node import NodeResponse
from app.utils import report, responses

router = APIRouter(tags=["User"], prefix="/api", responses={401: responses._401})


@router.post("/user", response_model=UserResponse, responses={400: responses._400, 409: responses._409})
def add_user(
    new_user: UserCreate,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """
    Add a new user
    (docstring remains the same)
    """
    generated_account_number = new_user.account_number if new_user.account_number else str(uuid.uuid4())

    for proxy_type in new_user.proxies:
        if not xray.config.inbounds_by_protocol.get(proxy_type):
            raise HTTPException(
                status_code=400,
                detail=f"Protocol {proxy_type} is disabled on your server",
            )

    # Fetch the ORM Admin model for the current admin
    db_admin_orm = crud.get_admin(db, current_admin.username)
    if not db_admin_orm:
        # This case should ideally be handled by Admin.get_current if it validates existence
        raise HTTPException(status_code=403, detail="Performing admin not found in database.")

    try:
        # Pass the ORM admin model to crud.create_user
        db_user_orm = crud.create_user(
            db, account_number=generated_account_number, user=new_user, admin=db_admin_orm
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="User with this account number or details already exists")

    bg.add_task(xray.operations.add_user, dbuser=db_user_orm)

    # For reporting, if it expects Pydantic models, convert.
    # db_user_orm.admin is the ORM Admin object.
    report.user_created(user=UserResponse.model_validate(db_user_orm), user_id=db_user_orm.id, by=current_admin, user_admin=db_user_orm.admin)
    logger.info(f'New user with account number "{db_user_orm.account_number}" added')
    return db_user_orm # FastAPI converts DBUser to UserResponse


@router.get("/user/{account_number}", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
def get_user(db_user_orm: DBUser = Depends(get_validated_user)): # Renamed for clarity
    """Get user information by account number"""
    return db_user_orm # FastAPI converts DBUser to UserResponse


@router.put("/user/{account_number}", response_model=UserResponse, responses={400: responses._400, 403: responses._403, 404: responses._404})
def modify_user(
    modified_user: UserModify,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user), # Renamed for clarity
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """
    Modify an existing user
    (docstring remains the same)
    """
    for proxy_type in modified_user.proxies:
        if not xray.config.inbounds_by_protocol.get(proxy_type):
            raise HTTPException(
                status_code=400,
                detail=f"Protocol {proxy_type} is disabled on your server",
            )

    old_status = db_user_orm.status
    dbuser_updated_orm = crud.update_user(db, db_user_orm, modified_user)

    # FastAPI will convert dbuser_updated_orm to UserResponse for the final HTTP response.
    # For internal operations like xray tasks, pass the ORM model.
    if dbuser_updated_orm.status in [UserStatus.active, UserStatus.on_hold]:
        bg.add_task(xray.operations.update_user, dbuser=dbuser_updated_orm)
    else:
        bg.add_task(xray.operations.remove_user, dbuser=dbuser_updated_orm)

    # For reporting, ensure types are what report function expects.
    # dbuser_updated_orm.admin is the ORM Admin object.
    report.user_updated(user=UserResponse.model_validate(dbuser_updated_orm), user_admin=dbuser_updated_orm.admin, by=current_admin)
    logger.info(f'User "{dbuser_updated_orm.account_number}" modified')

    if dbuser_updated_orm.status != old_status:
        report.status_change(
            account_number=dbuser_updated_orm.account_number,
            status=dbuser_updated_orm.status,
            user=UserResponse.model_validate(dbuser_updated_orm),
            user_admin=dbuser_updated_orm.admin,
            by=current_admin,
        )
        logger.info(
            f'User "{dbuser_updated_orm.account_number}" status changed from {old_status} to {dbuser_updated_orm.status}'
        )
    return dbuser_updated_orm # FastAPI converts DBUser to UserResponse


@router.delete("/user/{account_number}", responses={403: responses._403, 404: responses._404})
def remove_user(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user), # Renamed for clarity
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Remove a user by account number"""
    # db_user_orm is the ORM model from get_validated_user
    user_account_number = db_user_orm.account_number # Store before deletion if needed for logs
    user_admin_orm = db_user_orm.admin # Store admin ORM object before deletion

    crud.remove_user(db, db_user_orm)
    bg.add_task(xray.operations.remove_user, dbuser=db_user_orm) # Pass the ORM model

    # PydanticAdmin.model_validate might be needed if report expects Pydantic model
    # However, user_admin_orm is already the ORM Admin object.
    # If report.user_deleted expects PydanticAdmin, then use PydanticAdmin.model_validate(user_admin_orm) if user_admin_orm else None
    report.user_deleted(account_number=user_account_number, user_admin=user_admin_orm, by=current_admin)
    logger.info(f'User "{user_account_number}" deleted')
    return {"detail": "User successfully deleted"}


@router.post("/user/{account_number}/reset", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
def reset_user_data_usage(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user), # Renamed for clarity
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Reset user data usage by account number"""
    dbuser_reset_orm = crud.reset_user_data_usage(db=db, dbuser=db_user_orm)
    if dbuser_reset_orm.status in [UserStatus.active, UserStatus.on_hold]:
        bg.add_task(xray.operations.add_user, dbuser=dbuser_reset_orm)

    # dbuser_reset_orm.admin is the ORM Admin object
    report.user_data_usage_reset(user=UserResponse.model_validate(dbuser_reset_orm), user_admin=dbuser_reset_orm.admin, by=current_admin)
    logger.info(f'User "{dbuser_reset_orm.account_number}"\'s usage was reset')
    return dbuser_reset_orm # FastAPI converts DBUser to UserResponse


@router.post("/user/{account_number}/revoke_sub", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
def revoke_user_subscription(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user), # Renamed for clarity
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Revoke user's subscription by account number"""
    dbuser_revoked_orm = crud.revoke_user_sub(db=db, dbuser=db_user_orm)

    if dbuser_revoked_orm.status in [UserStatus.active, UserStatus.on_hold]:
        bg.add_task(xray.operations.update_user, dbuser=dbuser_revoked_orm)

    # dbuser_revoked_orm.admin is the ORM Admin object
    report.user_subscription_revoked(user=UserResponse.model_validate(dbuser_revoked_orm), user_admin=dbuser_revoked_orm.admin, by=current_admin)
    logger.info(f'User "{dbuser_revoked_orm.account_number}" subscription revoked')
    return dbuser_revoked_orm # FastAPI converts DBUser to UserResponse


@router.get("/users", response_model=UsersResponse, responses={400: responses._400, 403: responses._403, 404: responses._404})
def get_users(
    offset: int = None,
    limit: int = None,
    search: Union[str, None] = None,
    owner: Union[List[str], None] = Query(None, alias="admin"), # List of admin usernames
    status: UserStatus = None,
    sort: str = None,
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Get all users"""
    sort_options_enum_list = [] # Renamed
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

    # crud.get_users expects a list of admin usernames for the 'admins' filter.
    admin_usernames_filter = owner if current_admin.is_sudo else [current_admin.username]

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
    # FastAPI will convert each ORM user in users_orm_list to UserResponse
    return {"users": users_orm_list, "total": count}


@router.post("/users/reset", responses={403: responses._403, 404: responses._404})
def reset_users_data_usage(
    db: Session = Depends(get_db), current_admin: PydanticAdmin = Depends(PydanticAdmin.check_sudo_admin)
):
    """Reset all users data usage"""
    # crud.reset_all_users_data_usage expects an ORM Admin model or None
    db_admin_orm = crud.get_admin(db, current_admin.username)
    if not db_admin_orm and not current_admin.is_sudo: # Should be caught by check_sudo_admin or ensure admin exists
        raise HTTPException(status_code=403, detail="Admin performing action not found.")

    crud.reset_all_users_data_usage(db=db, admin=db_admin_orm if not current_admin.is_sudo else None)
    startup_config = xray.config.include_db_users() # Assuming this returns a valid config
    xray.core.restart(startup_config)
    for node_id, node in list(xray.nodes.items()): # Make a copy if modifying dict during iteration
        if node.connected: # Check if node object has 'connected' attribute
            xray.operations.restart_node(node_id, startup_config) # Ensure node_id and config are correct
    return {"detail": "Users successfully reset."}


@router.get("/user/{account_number}/usage", response_model=UserUsagesResponse, responses={403: responses._403, 404: responses._404})
def get_user_usage(
    db_user_orm: DBUser = Depends(get_validated_user), # Renamed, gets ORM User
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db),
):
    """Get user's usage by account number"""
    start_dt_obj, end_dt_obj = validate_dates(start, end) # Renamed

    usages = crud.get_user_usages(db, db_user_orm, start_dt_obj, end_dt_obj)
    return {"usages": usages, "account_number": db_user_orm.account_number}


@router.post("/user/{account_number}/active-next", response_model=UserResponse, responses={403: responses._403, 404: responses._404})
def active_next_plan(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    db_user_orm: DBUser = Depends(get_validated_user), # Renamed, gets ORM User
):
    """Reset user by next plan, identified by account number"""
    if db_user_orm.next_plan is None: # Check directly on the ORM model
        raise HTTPException(
            status_code=404,
            detail=f"User doesn't have next plan",
        )

    dbuser_reset_orm = crud.reset_user_by_next(db=db, dbuser=db_user_orm)
    # crud.reset_user_by_next should not return None if a plan existed, but good to be defensive
    if dbuser_reset_orm is None:
         raise HTTPException(status_code=500, detail="Failed to reset user by next plan")


    if dbuser_reset_orm.status in [UserStatus.active, UserStatus.on_hold]:
        bg.add_task(xray.operations.add_user, dbuser=dbuser_reset_orm)

    # dbuser_reset_orm.admin is the ORM Admin object
    report.user_data_reset_by_next(user=UserResponse.model_validate(dbuser_reset_orm), user_admin=dbuser_reset_orm.admin)
    logger.info(f'User "{dbuser_reset_orm.account_number}"\'s usage was reset by next plan')
    return dbuser_reset_orm # FastAPI converts DBUser to UserResponse


@router.get("/users/usage", response_model=UsersUsagesResponse)
def get_users_usage(
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db),
    owner: Union[List[str], None] = Query(None, alias="admin"), # List of admin usernames
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Get all users usage"""
    start_dt_obj, end_dt_obj = validate_dates(start, end) # Renamed

    admin_usernames_filter = owner if current_admin.is_sudo else [current_admin.username]
    usages = crud.get_all_users_usages(
        db=db, start=start_dt_obj, end=end_dt_obj, admin_usernames=admin_usernames_filter
    )
    return {"usages": usages}


@router.put("/user/{account_number}/set-owner", response_model=UserResponse)
def set_owner(
    admin_username_body: str,
    db_user_orm: DBUser = Depends(get_validated_user), # Renamed, gets ORM User
    db: Session = Depends(get_db),
    # current_admin is the one performing the action, checked by Depends(PydanticAdmin.check_sudo_admin)
    performing_admin: PydanticAdmin = Depends(PydanticAdmin.check_sudo_admin),
):
    """Set a new owner (admin) for a user, identified by account number."""
    new_admin_orm = crud.get_admin(db, username=admin_username_body) # Get new owner ORM model
    if not new_admin_orm:
        raise HTTPException(status_code=404, detail="New admin not found")

    dbuser_updated_orm = crud.set_owner(db, db_user_orm, new_admin_orm) # Pass ORM models
    logger.info(f'User "{dbuser_updated_orm.account_number}" owner successfully set to "{new_admin_orm.username}"')
    return dbuser_updated_orm # FastAPI converts DBUser to UserResponse


@router.get("/users/expired", response_model=List[str])
def get_expired_users(
    expired_after: Optional[datetime] = Query(None, example="2024-01-01T00:00:00"),
    expired_before: Optional[datetime] = Query(None, example="2024-01-31T23:59:59"),
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Get account numbers of users who have expired within the specified date range."""
    dt_expired_after_obj, dt_expired_before_obj = validate_dates(expired_after, expired_before) # Renamed

    # get_expired_users_list expects Pydantic Admin model
    expired_users_orm_list = get_expired_users_list(db, current_admin, dt_expired_after_obj, dt_expired_before_obj)
    return [u.account_number for u in expired_users_orm_list]


@router.delete("/users/expired", response_model=List[str])
def delete_expired_users(
    bg: BackgroundTasks,
    expired_after: Optional[datetime] = Query(None, example="2024-01-01T00:00:00"),
    expired_before: Optional[datetime] = Query(None, example="2024-01-31T23:59:59"),
    db: Session = Depends(get_db),
    current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current),
):
    """Delete users who have expired within the specified date range. Returns their account numbers."""
    dt_expired_after_obj, dt_expired_before_obj = validate_dates(expired_after, expired_before) # Renamed

    # get_expired_users_list expects Pydantic Admin model, returns list of ORM Users
    expired_users_orm_list = get_expired_users_list(db, current_admin, dt_expired_after_obj, dt_expired_before_obj)

    if not expired_users_orm_list:
        raise HTTPException(
            status_code=404, detail="No expired users found in the specified date range"
        )

    removed_users_account_numbers = [u.account_number for u in expired_users_orm_list]
    crud.remove_users(db, expired_users_orm_list) # Pass list of ORM user objects

    for removed_user_orm in expired_users_orm_list:
        logger.info(f'User with account number "{removed_user_orm.account_number}" deleted')
        # removed_user_orm.admin is the ORM Admin object associated with the deleted user
        bg.add_task(
            report.user_deleted,
            account_number=removed_user_orm.account_number,
            user_admin=removed_user_orm.admin, # Pass the ORM admin model of the user's owner
            by=current_admin, # Pydantic model of admin performing action
        )
    return removed_users_account_numbers


@router.get("/user/{account_number}/nodes", response_model=List[NodeResponse])
def get_user_nodes(
    db_user_orm: DBUser = Depends(get_validated_user), # Gets ORM User
    # current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current), # Not strictly needed if validation is in get_validated_user
):
    """Get the list of nodes selected by the user, identified by account number."""
    # Assuming db_user_orm.selected_nodes is a list of UserNodeSelection ORM objects,
    # and each selection has a 'node' attribute which is the Node ORM object.
    # FastAPI will convert each Node ORM object to NodeResponse.
    return [selection.node for selection in db_user_orm.selected_nodes]


@router.post("/user/{account_number}/nodes/{node_id}", response_model=UserResponse)
def add_user_node(
    node_id: int,
    db_user_orm: DBUser = Depends(get_validated_user), # Gets ORM User
    db: Session = Depends(get_db),
    # current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current), # Not strictly needed
):
    """Add a node to the user's selected nodes, user identified by account number."""
    node_orm = crud.get_node_by_id(db, node_id) # crud.get_node or crud.get_node_by_id
    if not node_orm:
        raise HTTPException(status_code=404, detail="Node not found")

    if any(selection.node_id == node_id for selection in db_user_orm.selected_nodes):
        raise HTTPException(status_code=409, detail="Node already selected by this user")

    crud.add_user_node(db, db_user_orm, node_orm) # Pass ORM models

    # Re-fetch to ensure relationships are correctly loaded for the response
    updated_db_user_orm = crud.get_user(db, account_number=db_user_orm.account_number)
    return updated_db_user_orm # FastAPI converts to UserResponse


@router.delete("/user/{account_number}/nodes/{node_id}", response_model=UserResponse)
def remove_user_node(
    node_id: int,
    db_user_orm: DBUser = Depends(get_validated_user), # Gets ORM User
    db: Session = Depends(get_db),
    # current_admin: PydanticAdmin = Depends(PydanticAdmin.get_current), # Not strictly needed
):
    """Remove a node from the user's selected nodes, user identified by account number."""
    node_orm = crud.get_node_by_id(db, node_id) # crud.get_node or crud.get_node_by_id
    if not node_orm:
        raise HTTPException(status_code=404, detail="Node not found")

    if not any(selection.node_id == node_id for selection in db_user_orm.selected_nodes):
        raise HTTPException(status_code=404, detail="Node not selected by this user")

    crud.remove_user_node(db, db_user_orm, node_orm) # Pass ORM models

    updated_db_user_orm = crud.get_user(db, account_number=db_user_orm.account_number)
    return updated_db_user_orm # FastAPI converts to UserResponse