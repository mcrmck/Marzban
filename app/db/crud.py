"""
Functions for managing proxy hosts, users, user templates, nodes, and administrative tasks.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

from sqlalchemy import and_, delete, func, or_
from sqlalchemy.orm import Query, Session, joinedload
from sqlalchemy.sql.functions import coalesce

from app.db.models import (
    JWT,
    TLS,
    Admin,
    AdminUsageLogs,
    NextPlan,
    Node,
    NodeUsage,
    NodeUserUsage,
    NotificationReminder,
    Proxy,
    ProxyHost,
    ProxyInbound,
    # ProxyTypes, # Not directly used here, but by models.py
    System,
    User,
    # UserNodeSelection, # Removed model
    UserTemplate,
    UserUsageResetLogs,
)
from app.models.admin import AdminCreate, AdminModify, AdminPartialModify
from app.models.node import NodeCreate, NodeModify, NodeStatus, NodeUsageResponse
from app.models.proxy import ProxyHost as ProxyHostModify
from app.models.proxy import ProxyTypes # Import if needed for type hints or direct use
from app.models.user import (
    ReminderType,
    UserCreate,
    UserDataLimitResetStrategy,
    UserModify,
    UserResponse, # Used in revoke_user_sub
    UserStatus,
    UserUsageResponse
)
from app.models.user_template import UserTemplateCreate, UserTemplateModify
from app.utils.helpers import calculate_expiration_days, calculate_usage_percent
from config import NOTIFY_DAYS_LEFT, NOTIFY_REACHED_USAGE_PERCENT, USERS_AUTODELETE_DAYS


def add_default_host(db: Session, inbound: ProxyInbound):
    """
    Adds a default host to a proxy inbound.

    Args:
        db (Session): Database session.
        inbound (ProxyInbound): Proxy inbound to add the default host to.
    """
    host = ProxyHost(remark="🚀 Marz ({USERNAME}) [{PROTOCOL} - {TRANSPORT}]", address="{SERVER_IP}", inbound=inbound)
    db.add(host)
    db.commit()


def get_or_create_inbound(db: Session, inbound_tag: str) -> ProxyInbound:
    """
    Retrieves or creates a proxy inbound based on the given tag.

    Args:
        db (Session): Database session.
        inbound_tag (str): The tag of the inbound.

    Returns:
        ProxyInbound: The retrieved or newly created proxy inbound.
    """
    inbound = db.query(ProxyInbound).filter(ProxyInbound.tag == inbound_tag).first()
    if not inbound:
        inbound = ProxyInbound(tag=inbound_tag)
        db.add(inbound)
        db.commit()
        add_default_host(db, inbound)
        db.refresh(inbound)
    return inbound


def get_hosts(db: Session, inbound_tag: str) -> List[ProxyHost]:
    """
    Retrieves hosts for a given inbound tag.

    Args:
        db (Session): Database session.
        inbound_tag (str): The tag of the inbound.

    Returns:
        List[ProxyHost]: List of hosts for the inbound.
    """
    inbound = get_or_create_inbound(db, inbound_tag)
    return inbound.hosts


def add_host(db: Session, inbound_tag: str, host: ProxyHostModify) -> List[ProxyHost]:
    """
    Adds a new host to a proxy inbound.

    Args:
        db (Session): Database session.
        inbound_tag (str): The tag of the inbound.
        host (ProxyHostModify): Host details to be added.

    Returns:
        List[ProxyHost]: Updated list of hosts for the inbound.
    """
    inbound = get_or_create_inbound(db, inbound_tag)
    new_db_host = ProxyHost( # Renamed to avoid conflict with host argument
            remark=host.remark,
            address=host.address,
            port=host.port,
            path=host.path,
            sni=host.sni,
            host=host.host, # This is ProxyHostModify.host which is the HTTP host header
            inbound=inbound,
            security=host.security,
            alpn=host.alpn,
            fingerprint=host.fingerprint
        )
    inbound.hosts.append(new_db_host)
    db.commit()
    db.refresh(inbound)
    return inbound.hosts


def update_hosts(db: Session, inbound_tag: str, modified_hosts: List[ProxyHostModify]) -> List[ProxyHost]:
    """
    Updates hosts for a given inbound tag. This replaces all existing hosts for the inbound.

    Args:
        db (Session): Database session.
        inbound_tag (str): The tag of the inbound.
        modified_hosts (List[ProxyHostModify]): List of modified hosts.

    Returns:
        List[ProxyHost]: Updated list of hosts for the inbound.
    """
    inbound = get_or_create_inbound(db, inbound_tag)
    # Clear existing hosts first by assigning an empty list or deleting them
    # For simple replacement:
    inbound.hosts.clear() # Or delete existing host objects if cascade isn't set up to do so upon clear
    db.flush() # Ensure deletes are processed before adding new ones if there are unique constraints

    new_host_objects = []
    for host_data in modified_hosts:
        new_db_host = ProxyHost(
            remark=host_data.remark,
            address=host_data.address,
            port=host_data.port,
            path=host_data.path,
            sni=host_data.sni,
            host=host_data.host, # HTTP Host header from ProxyHostModify
            inbound_tag=inbound.tag, # Explicitly set if inbound relationship isn't enough or for clarity
            # inbound=inbound, # Relationship should handle this if appended
            security=host_data.security,
            alpn=host_data.alpn,
            fingerprint=host_data.fingerprint,
            allowinsecure=host_data.allowinsecure,
            is_disabled=host_data.is_disabled,
            mux_enable=host_data.mux_enable,
            fragment_setting=host_data.fragment_setting,
            noise_setting=host_data.noise_setting,
            random_user_agent=host_data.random_user_agent,
            use_sni_as_host=host_data.use_sni_as_host,
        )
        new_host_objects.append(new_db_host)

    inbound.hosts.extend(new_host_objects) # Add all new hosts

    db.commit()
    db.refresh(inbound) # Refresh to get the updated list with IDs etc.
    return inbound.hosts


def get_user_queryset(db: Session) -> Query:
    """
    Retrieves the base user query with joinedload for admin, next_plan, proxies, and usage_logs.
    This helps prevent DetachedInstanceErrors when these relationships are accessed later,
    especially if the User object is passed to background tasks or other contexts
    where the original session might be closed.

    Args:
        db (Session): Database session.

    Returns:
        Query: Base user query with eagerly loaded relationships.
    """
    return db.query(User).options(
        joinedload(User.admin),
        joinedload(User.next_plan),
        joinedload(User.proxies),      # Eager load proxies
        joinedload(User.usage_logs)    # Eager load usage_logs (for lifetime_used_traffic)
    )


def get_user(db: Session, account_number: str) -> Optional[User]:
    """
    Retrieves a user by account number (case-insensitive for the input),
    with related admin, next_plan, proxies, and usage_logs eagerly loaded.
    """
    # Debug prints from user, kept for now
    print(f"[DEBUG] crud.get_user: original input account_number: '{account_number}' (type: {type(account_number)})")

    account_number_to_query = account_number.lower()
    print(f"[DEBUG] crud.get_user: attempting to find user with lowercase account_number: '{account_number_to_query}'")

    db_user = get_user_queryset(db).filter(User.account_number == account_number_to_query).first()

    if db_user:
        print(f"[DEBUG] crud.get_user: Found user: {db_user.id}, {db_user.account_number}")
    else:
        print(f"[DEBUG] crud.get_user: No user found for account_number: '{account_number_to_query}'")

    return db_user


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    Retrieves a user by user ID, with related admin, next_plan, proxies, and usage_logs eagerly loaded.

    Args:
        db (Session): Database session.
        user_id (int): The ID of the user.

    Returns:
        Optional[User]: The user object if found, else None.
    """
    return get_user_queryset(db).filter(User.id == user_id).first()


UsersSortingOptions = Enum('UsersSortingOptions', {
    'account_number': User.account_number.asc(),
    'used_traffic': User.used_traffic.asc(),
    'data_limit': User.data_limit.asc(),
    'expire': User.expire.asc(),
    'created_at': User.created_at.asc(),
    '-account_number': User.account_number.desc(),
    '-used_traffic': User.used_traffic.desc(),
    '-data_limit': User.data_limit.desc(),
    '-expire': User.expire.desc(),
    '-created_at': User.created_at.desc(),
})


def get_users(db: Session,
              offset: Optional[int] = None,
              limit: Optional[int] = None,
              account_numbers: Optional[List[str]] = None, # Changed from usernames
              search: Optional[str] = None,
              status: Optional[Union[UserStatus, list]] = None,
              sort: Optional[List[UsersSortingOptions]] = None,
              admin: Optional[Admin] = None, # Specific Admin ORM object
              admins: Optional[List[str]] = None, # List of admin usernames
              reset_strategy: Optional[Union[UserDataLimitResetStrategy, list]] = None,
              return_with_count: bool = False) -> Union[List[User], Tuple[List[User], int]]:
    """
    Retrieves users based on various filters and options, with related data eagerly loaded.
    """
    query = get_user_queryset(db)

    if account_numbers:
        # Ensure account numbers are queried in lowercase if they are stored as such
        lowercase_account_numbers = [acc_num.lower() for acc_num in account_numbers]
        query = query.filter(User.account_number.in_(lowercase_account_numbers))

    if search: # Add search functionality if it was missing or adapt
        search_term = f"%{search.lower()}%"
        query = query.filter(
            or_(
                User.account_number.ilike(search_term), # Search by account number
                User.note.ilike(search_term)             # Search by note
            )
        )

    if status:
        if isinstance(status, list):
            query = query.filter(User.status.in_(status))
        else:
            query = query.filter(User.status == status)

    if reset_strategy:
        if isinstance(reset_strategy, list):
            query = query.filter(User.data_limit_reset_strategy.in_(reset_strategy))
        else:
            query = query.filter(User.data_limit_reset_strategy == reset_strategy)

    if admin: # Filter by specific Admin ORM object
        query = query.filter(User.admin_id == admin.id) # Assuming User.admin_id exists

    if admins: # Filter by list of admin usernames
        query = query.join(User.admin).filter(Admin.username.in_(admins))


    count_query = query # Store query before applying order, offset, limit for count

    if sort:
        # Ensure sort options are applied correctly. Example: query.order_by(User.created_at.desc())
        # The UsersSortingOptions enum approach is fine if opt.value is the SQLAlchemy sort expression
        query = query.order_by(*(opt.value for opt in sort))

    if offset is not None: # Check for None explicitly
        query = query.offset(offset)
    if limit is not None: # Check for None explicitly
        query = query.limit(limit)

    if return_with_count:
        # Use the query before ordering and pagination for a correct total count
        # Count distinct users if joins might produce multiple rows per user before distinct()
        # However, get_user_queryset is db.query(User)... so it should be fine.
        total_count = count_query.distinct(User.id).count()
        return query.all(), total_count

    return query.all()


def get_user_usages(db: Session, dbuser: User, start: datetime, end: datetime) -> List[UserUsageResponse]:
    """
    Retrieves user usages within a specified date range.

    Args:
        db (Session): Database session.
        dbuser (User): The user object.
        start (datetime): Start date for usage retrieval.
        end (datetime): End date for usage retrieval.

    Returns:
        List[UserUsageResponse]: List of user usage responses.
    """

    usages: Dict[Union[int, None], UserUsageResponse] = { # Type hint for dict key
        0: UserUsageResponse(  # Main Core (assuming 0 is a conventional ID for master/core if node_id is nullable)
            node_id=None, # Explicitly None for Master
            node_name="Master",
            used_traffic=0
        )
    }

    for node in db.query(Node).all():
        usages[node.id] = UserUsageResponse(
            node_id=node.id,
            node_name=node.name,
            used_traffic=0
        )

    cond = and_(NodeUserUsage.user_id == dbuser.id,
                NodeUserUsage.created_at >= start,
                NodeUserUsage.created_at <= end)

    for v in db.query(NodeUserUsage).filter(cond):
        # Use v.node_id directly. If it's None, it should map to key 0 (Master)
        key_to_use = v.node_id if v.node_id is not None else 0
        if key_to_use in usages:
            usages[key_to_use].used_traffic += v.used_traffic
        # else: # Optionally handle case where node_id from usage log isn't in pre-populated usages dict
        #     print(f"Warning: Usage logged for unknown node_id {v.node_id}")


    return list(usages.values())


def get_users_count(db: Session, status: Optional[UserStatus] = None, admin: Optional[Admin] = None) -> int:
    """
    Retrieves the count of users based on status and admin filters.

    Args:
        db (Session): Database session.
        status (UserStatus, optional): Status to filter users by.
        admin (Admin, optional): Admin to filter users by.

    Returns:
        int: Count of users matching the criteria.
    """
    query = db.query(func.count(User.id)) # Use func.count for efficiency
    if admin:
        query = query.filter(User.admin_id == admin.id) # Filter by admin_id
    if status:
        query = query.filter(User.status == status)
    return query.scalar() or 0 # Use scalar() instead of scalar_one() and handle None case


def create_user(db: Session, account_number: str, user: UserCreate, admin: Optional[Admin] = None) -> User:
    """
    Creates a new user with provided details.
    Returns the created user object, with relationships potentially needing eager loading
    if passed directly to background tasks that then create Pydantic models.
    Consider re-fetching with get_user_by_id if full eager loading is needed immediately.
    """
    proxies_list = [] # Renamed to avoid conflict
    for proxy_type_enum, settings_model in user.proxies.items():
        proxies_list.append(
            Proxy(
                type=proxy_type_enum, # Store enum directly if column type supports it, or .value
                settings=settings_model.model_dump(exclude_none=True) # Use model_dump for Pydantic v2
            )
        )

    next_plan_orm = None
    if user.next_plan:
        next_plan_orm = NextPlan(
            data_limit=user.next_plan.data_limit,
            expire=user.next_plan.expire,
            add_remaining_traffic=user.next_plan.add_remaining_traffic,
            fire_on_either=user.next_plan.fire_on_either,
        )

    dbuser = User(
        account_number=account_number.lower(), # Store lowercase
        proxies=proxies_list,
        status=user.status,
        data_limit=(user.data_limit if user.data_limit is not None else None), # Ensure 0 is preserved
        expire=(user.expire if user.expire is not None else None),
        admin_id=admin.id if admin else None, # Assign admin_id
        # admin=admin, # Relationship will be set via admin_id and backref if configured
        data_limit_reset_strategy=user.data_limit_reset_strategy,
        note=user.note,
        on_hold_expire_duration=(user.on_hold_expire_duration if user.on_hold_expire_duration is not None else None),
        on_hold_timeout=(user.on_hold_timeout if user.on_hold_timeout is not None else None),
        auto_delete_in_days=user.auto_delete_in_days,
        next_plan=next_plan_orm
    )
    db.add(dbuser)
    db.commit()
    db.refresh(dbuser) # Refresh to get IDs and load default values

    # For full eager loading consistent with get_user, re-fetch:
    # return get_user_by_id(db, dbuser.id)
    # However, for now, returning the refreshed instance. Callers should be aware if using in background tasks.
    return dbuser


def remove_user(db: Session, dbuser: User) -> User:
    """
    Removes a user from the database.

    Args:
        db (Session): Database session.
        dbuser (User): The user object to be removed.

    Returns:
        User: The (detached) user object that was removed.
    """
    db.delete(dbuser)
    db.commit()
    return dbuser


def remove_users(db: Session, dbusers: List[User]):
    """
    Removes multiple users from the database.

    Args:
        db (Session): Database session.
        dbusers (List[User]): List of user objects to be removed.
    """
    for dbuser in dbusers:
        db.delete(dbuser)
    db.commit()
    # No return needed, or return the list of (detached) users if required by caller
    return


def update_user(db: Session, dbuser: User, modify: UserModify) -> User:
    """
    Updates a user with new details.
    The dbuser passed in should ideally be fetched with get_user_queryset for eager loading.
    """
    # Update proxies
    if modify.proxies is not None: # Check if proxies field is present in modify payload
        current_proxy_types_in_db = {p.type for p in dbuser.proxies}
        modify_proxy_types = set(modify.proxies.keys())

        # Add or Update proxies
        for proxy_type_enum, settings_model in modify.proxies.items():
            existing_proxy = next((p for p in dbuser.proxies if p.type == proxy_type_enum), None)
            if existing_proxy:
                existing_proxy.settings = settings_model.model_dump(exclude_none=True)
            else:
                new_proxy = Proxy(
                    type=proxy_type_enum,
                    settings=settings_model.model_dump(exclude_none=True),
                    user_id=dbuser.id # Explicitly set user_id
                )
                dbuser.proxies.append(new_proxy) # Add to relationship collection

        # Remove proxies not in modify payload
        proxies_to_remove = [p for p in dbuser.proxies if p.type not in modify_proxy_types]
        for p_to_remove in proxies_to_remove:
            db.delete(p_to_remove) # Delete from session
            # dbuser.proxies.remove(p_to_remove) # Also remove from collection if not cascaded by delete

    # Update scalar fields
    update_data = modify.model_dump(exclude_unset=True, exclude={'proxies'}) # Get other fields

    original_status = dbuser.status # Store for later comparison

    for key, value in update_data.items():
        if key == "next_plan": # Handle nested NextPlan separately
            if value is None: # If next_plan is explicitly set to null
                if dbuser.next_plan:
                    db.delete(dbuser.next_plan)
                    dbuser.next_plan = None
            else: # If next_plan data is provided
                if dbuser.next_plan: # Update existing
                    for np_key, np_value in value.items():
                        setattr(dbuser.next_plan, np_key, np_value)
                else: # Create new
                    dbuser.next_plan = NextPlan(**value, user_id=dbuser.id)
        elif hasattr(dbuser, key):
            setattr(dbuser, key, value)
            # Special handling for status changes and dependent reminders
            if key == "status" and value != original_status:
                dbuser.last_status_change = datetime.utcnow()

            if key == "data_limit":
                if dbuser.status not in (UserStatus.expired, UserStatus.disabled):
                    if not value or (dbuser.used_traffic < value if value is not None else True): # Check against new data_limit
                        if dbuser.status == UserStatus.limited and dbuser.status != UserStatus.on_hold: # If un-limiting
                            setattr(dbuser, 'status', UserStatus.active) # Set status to active
                    elif value is not None and dbuser.used_traffic >= value: # If new limit makes user limited
                        setattr(dbuser, 'status', UserStatus.limited)
                # Clear data usage reminders if limit changes
                if value is not None:
                    for percent in sorted(NOTIFY_REACHED_USAGE_PERCENT, reverse=True):
                        delete_notification_reminder_by_type(db, dbuser.id, ReminderType.data_usage, threshold=percent)


            if key == "expire":
                if dbuser.status in (UserStatus.active, UserStatus.expired, UserStatus.limited): # Check if status could change due to expire
                    if not value or (datetime.fromtimestamp(value) > datetime.utcnow() if value is not None else True): # Check new expire
                        if dbuser.status == UserStatus.expired: # If un-expiring
                             setattr(dbuser, 'status', UserStatus.active)
                    elif value is not None and datetime.fromtimestamp(value) <= datetime.utcnow(): # If new expire makes user expired
                        setattr(dbuser, 'status', UserStatus.expired)
                # Clear expiration reminders if expire date changes
                if value is not None:
                    for days_left in sorted(NOTIFY_DAYS_LEFT):
                        delete_notification_reminder_by_type(db, dbuser.id, ReminderType.expiration_date, threshold=days_left)


    if 'status' in update_data and dbuser.status != original_status:
        dbuser.last_status_change = datetime.utcnow() # Ensure last_status_change is updated if status changed directly

    dbuser.edit_at = datetime.utcnow()

    db.commit()
    db.refresh(dbuser)
    # For full eager loading consistent with get_user, re-fetch:
    # return get_user_by_id(db, dbuser.id)
    return dbuser


def reset_user_data_usage(db: Session, dbuser: User) -> User:
    """
    Resets the data usage of a user and logs the reset.
    """
    usage_log = UserUsageResetLogs(
        user_id=dbuser.id, # Set user_id directly
        used_traffic_at_reset=dbuser.used_traffic,
    )
    db.add(usage_log)

    dbuser.used_traffic = 0

    # Clear specific NodeUserUsage records
    db.query(NodeUserUsage).filter(NodeUserUsage.user_id == dbuser.id).delete(synchronize_session=False)

    if dbuser.status not in (UserStatus.expired, UserStatus.disabled, UserStatus.on_hold): # Keep on_hold status
        # If user was limited due to data, and data_limit exists, make active.
        # Otherwise, status might depend on other factors like expire.
        if dbuser.data_limit is None or dbuser.data_limit > 0 : # only make active if there's a limit or no limit
            dbuser.status = UserStatus.active

    if dbuser.next_plan: # If resetting usage, typically next_plan should be cleared
        db.delete(dbuser.next_plan)
        dbuser.next_plan = None

    db.add(dbuser) # dbuser is already in session, this is more like a flush marker
    db.commit()
    db.refresh(dbuser)
    # return get_user_by_id(db, dbuser.id) # Re-fetch with eager loads
    return dbuser


def reset_user_by_next(db: Session, dbuser: User) -> User:
    """
    Resets the data usage of a user based on their next_plan.
    """
    if dbuser.next_plan is None:
        # This should ideally be checked by the caller, but as a safeguard:
        return dbuser # Or raise an error

    usage_log = UserUsageResetLogs(
        user_id=dbuser.id,
        used_traffic_at_reset=dbuser.used_traffic,
    )
    db.add(usage_log)

    db.query(NodeUserUsage).filter(NodeUserUsage.user_id == dbuser.id).delete(synchronize_session=False)

    # Calculate remaining traffic if needed
    remaining_traffic = 0
    if dbuser.next_plan.add_remaining_traffic and dbuser.data_limit is not None:
        remaining_traffic = max(0, dbuser.data_limit - dbuser.used_traffic)

    dbuser.data_limit = dbuser.next_plan.data_limit + remaining_traffic if dbuser.next_plan.data_limit is not None else None
    dbuser.expire = dbuser.next_plan.expire

    dbuser.used_traffic = 0
    dbuser.status = UserStatus.active # Activating with new plan
    dbuser.last_status_change = datetime.utcnow()

    db.delete(dbuser.next_plan)
    dbuser.next_plan = None

    db.add(dbuser)
    db.commit()
    db.refresh(dbuser)
    # return get_user_by_id(db, dbuser.id) # Re-fetch with eager loads
    return dbuser


def revoke_user_sub(db: Session, dbuser: User) -> User:
    """
    Revokes the subscription of a user and updates proxies settings by regenerating their IDs.
    The dbuser passed in should be eagerly loaded.
    """
    dbuser.sub_revoked_at = datetime.utcnow()

    # If UserResponse.model_validate accesses lazy-loaded fields not covered by get_user_queryset,
    # this could still be an issue if dbuser is detached.
    # Assuming get_user_queryset covers necessary fields for UserResponse (like proxies).
    user_pydantic = UserResponse.model_validate(dbuser) # Create Pydantic model from (hopefully) loaded ORM obj

    new_proxy_settings_list = []
    for proxy_type, pydantic_proxy_settings in user_pydantic.proxies.items():
        pydantic_proxy_settings.revoke() # This method should modify the Pydantic model's settings (e.g., new UUID)
        new_proxy_settings_list.append({
            "type": proxy_type,
            "settings": pydantic_proxy_settings.model_dump(exclude_none=True)
        })

    # Update proxies in the database
    # Delete existing proxies
    for p in list(dbuser.proxies): # Iterate over a copy
        db.delete(p)
    db.flush() # Ensure deletes happen before adds if unique constraints matter on user_id+type

    # Add new proxies with revoked settings
    for new_proxy_data in new_proxy_settings_list:
        dbuser.proxies.append(
            Proxy(type=new_proxy_data["type"], settings=new_proxy_data["settings"])
        )

    db.commit()
    db.refresh(dbuser)
    # return get_user_by_id(db, dbuser.id) # Re-fetch with eager loads including new proxies
    return dbuser


def update_user_sub(db: Session, dbuser: User, user_agent: str) -> User:
    """
    Updates the user's subscription details (last update time and user agent).
    """
    dbuser.sub_updated_at = datetime.utcnow()
    dbuser.sub_last_user_agent = user_agent

    db.commit()
    db.refresh(dbuser)
    return dbuser


def reset_all_users_data_usage(db: Session, admin: Optional[Admin] = None):
    """
    Resets the data usage for all users or users under a specific admin.
    """
    query = get_user_queryset(db) # Get users with relations preloaded if needed for status logic

    if admin:
        query = query.filter(User.admin_id == admin.id)

    for dbuser_item in query.all(): # Renamed to avoid conflict
        dbuser_item.used_traffic = 0
        # Clear related NodeUserUsage records
        db.query(NodeUserUsage).filter(NodeUserUsage.user_id == dbuser_item.id).delete(synchronize_session=False)

        if dbuser_item.status not in [UserStatus.on_hold, UserStatus.expired, UserStatus.disabled]:
            dbuser_item.status = UserStatus.active

        # Assuming UserUsageResetLogs are not created for mass reset, or add logic if they are
        # dbuser_item.usage_logs.clear() # This would delete historical reset logs, be careful

        if dbuser_item.next_plan:
            db.delete(dbuser_item.next_plan)
            dbuser_item.next_plan = None
        # No db.add(dbuser_item) needed if modifying existing tracked objects
    db.commit()


def disable_all_active_users(db: Session, admin: Optional[Admin] = None):
    """
    Disable all active or on_hold users for a specific admin or all admins.
    """
    query = db.query(User).filter(User.status.in_([UserStatus.active, UserStatus.on_hold]))
    if admin:
        query = query.filter(User.admin_id == admin.id)

    query.update(
        {User.status: UserStatus.disabled, User.last_status_change: datetime.utcnow()},
        synchronize_session=False # Recommended for bulk updates
    )
    db.commit()


def activate_all_disabled_users(db: Session, admin: Optional[Admin] = None):
    """
    Activate all disabled users for a specific admin or all admins.
    Users who were on_hold (and are now disabled) might need special handling if they should return to on_hold.
    This implementation activates them to 'active'.
    """
    # Users that should become 'on_hold'
    # These are users currently 'disabled', had an on_hold_expire_duration, no specific expire date, and were not online.
    on_hold_criteria_users_query = db.query(User).filter(
        User.status == UserStatus.disabled,
        User.on_hold_expire_duration.isnot(None), # Had a duration for on_hold
        User.on_hold_timeout.isnot(None), # Indicates they were on hold
        # User.expire.is_(None), # This was part of original query for on_hold
        # User.online_at.is_(None) # This was part of original query for on_hold
    )

    # Users that should become 'active' (all other disabled users)
    active_criteria_users_query = db.query(User).filter(User.status == UserStatus.disabled)

    if admin:
        on_hold_criteria_users_query = on_hold_criteria_users_query.filter(User.admin_id == admin.id)
        active_criteria_users_query = active_criteria_users_query.filter(User.admin_id == admin.id)
        # Exclude users matched by on_hold_criteria from the active_criteria
        on_hold_user_ids = [u.id for u in on_hold_criteria_users_query.all()] # Get IDs first
        if on_hold_user_ids:
            active_criteria_users_query = active_criteria_users_query.filter(User.id.notin_(on_hold_user_ids))


    on_hold_criteria_users_query.update(
        {User.status: UserStatus.on_hold, User.last_status_change: datetime.utcnow()},
        synchronize_session=False
    )
    active_criteria_users_query.update(
        {User.status: UserStatus.active, User.last_status_change: datetime.utcnow()},
        synchronize_session=False
    )
    db.commit()


def autodelete_expired_users(db: Session,
                             include_limited_users: bool = False) -> List[User]:
    """
    Deletes expired (optionally also limited) users whose auto-delete time has passed.
    """
    target_status = (
        [UserStatus.expired, UserStatus.limited] if include_limited_users
        else [UserStatus.expired]
    )

    # Use coalesce for auto_delete_in_days, falling back to USERS_AUTODELETE_DAYS if user's setting is NULL
    effective_auto_delete_days = coalesce(User.auto_delete_in_days, USERS_AUTODELETE_DAYS)

    # Filter for users who are eligible for auto-deletion (non-negative auto_delete setting)
    # and whose last_status_change + auto_delete_days is in the past.
    # SQLAlchemy does not directly support arithmetic with INTERVAL 'X days' in a generic way for all DBs in filter.
    # So, fetching candidates and then filtering in Python is one approach, as was done.
    # For database-level filtering, one might need to use DB-specific functions.

    query = db.query(
        User, effective_auto_delete_days.label("effective_days")
    ).filter(
        effective_auto_delete_days >= 0,  # auto_delete_in_days is positive or zero, or global is
        User.status.in_(target_status),
    ).options(joinedload(User.admin)) # Eager load admin for reporting or other use after potential deletion

    users_to_delete = []
    for user, auto_delete_val in query.all():
        if user.last_status_change: # Ensure last_status_change is not None
            # auto_delete_val can be from user.auto_delete_in_days or USERS_AUTODELETE_DAYS
            if user.last_status_change + timedelta(days=auto_delete_val) <= datetime.utcnow():
                users_to_delete.append(user)

    if users_to_delete:
        # It's important to pass the list of actual User objects to remove_users
        remove_users(db, users_to_delete)

    return users_to_delete # Returns (now detached) user objects that were deleted


def get_all_users_usages( # Renamed parameter `admin` to `admin_filter_obj` for clarity
        db: Session, admin_filter_obj: Optional[Admin], start: datetime, end: datetime # admin can be None
) -> List[UserUsageResponse]:
    """
    Retrieves usage data for all users (optionally filtered by an admin) within a specified time range.
    """
    usages: Dict[Union[int, None], UserUsageResponse] = {
        0: UserUsageResponse(node_id=None, node_name="Master", used_traffic=0)
    }
    for node in db.query(Node).all():
        usages[node.id] = UserUsageResponse(node_id=node.id, node_name=node.name, used_traffic=0)

    # Build user ID filter based on admin_filter_obj
    user_id_filter_condition = None
    if admin_filter_obj:
        # Get IDs of users belonging to this admin
        admin_user_ids = db.query(User.id).filter(User.admin_id == admin_filter_obj.id).subquery()
        user_id_filter_condition = NodeUserUsage.user_id.in_(admin_user_ids)

    # Base condition for date range
    usage_query_conditions = [
        NodeUserUsage.created_at >= start,
        NodeUserUsage.created_at <= end
    ]
    if user_id_filter_condition is not None:
        usage_query_conditions.append(user_id_filter_condition)

    for v in db.query(NodeUserUsage).filter(and_(*usage_query_conditions)):
        key_to_use = v.node_id if v.node_id is not None else 0
        if key_to_use in usages: # Ensure the node_id exists in our prepared dict
            usages[key_to_use].used_traffic += v.used_traffic
        # else:
            # Optional: log if usage is found for a node_id not in the Node table (should not happen with FKs)
            # print(f"Warning: Usage found for unexpected node_id: {v.node_id}")


    return list(usages.values())


def update_user_status(db: Session, dbuser: User, status: UserStatus) -> User:
    """
    Updates a user's status and records the time of change.
    """
    if dbuser.status != status: # Only update if status actually changes
        dbuser.status = status
        dbuser.last_status_change = datetime.utcnow()
        db.commit()
        db.refresh(dbuser)
    return dbuser


def set_owner(db: Session, dbuser: User, admin: Admin) -> User:
    """
    Sets the owner (admin) of a user.
    """
    dbuser.admin_id = admin.id # Set by admin_id
    # dbuser.admin = admin # Relationship will update
    db.commit()
    db.refresh(dbuser)
    # return get_user_by_id(db, dbuser.id) # Re-fetch with eager loads
    return dbuser


def start_user_expire(db: Session, dbuser: User) -> User:
    """
    Starts the expiration timer for a user if they were on hold.
    """
    if dbuser.on_hold_expire_duration is not None: # Check if there was a duration
        expire_timestamp = int(datetime.utcnow().timestamp()) + dbuser.on_hold_expire_duration
        dbuser.expire = expire_timestamp
        dbuser.on_hold_expire_duration = None # Clear on_hold specific fields
        dbuser.on_hold_timeout = None
        if dbuser.status == UserStatus.on_hold : # If status was on_hold, make it active
            dbuser.status = UserStatus.active
            dbuser.last_status_change = datetime.utcnow()
        db.commit()
        db.refresh(dbuser)
    return dbuser


def get_system_usage(db: Session) -> Optional[System]: # Can be Optional if table is empty
    """
    Retrieves system usage information.
    """
    return db.query(System).first()


def get_jwt_secret_key(db: Session) -> Optional[str]: # Can be Optional
    """
    Retrieves the JWT secret key.
    """
    jwt_record = db.query(JWT).first()
    return jwt_record.secret_key if jwt_record else None


def get_tls_certificate(db: Session) -> Optional[TLS]: # Can be Optional
    """
    Retrieves the TLS certificate.
    """
    return db.query(TLS).first()


def get_admin(db: Session, username: str) -> Optional[Admin]: # Can be Optional
    """
    Retrieves an admin by username.
    """
    return db.query(Admin).filter(Admin.username == username).first()


def create_admin(db: Session, admin: AdminCreate) -> Admin:
    """
    Creates a new admin in the database.
    """
    dbadmin = Admin(
        username=admin.username,
        # Assuming AdminCreate has hashed_password, not plain password
        hashed_password=admin.password, # If AdminCreate.password is already hashed
        is_sudo=admin.is_sudo if admin.is_sudo is not None else False, # Default for is_sudo
        telegram_id=admin.telegram_id, # Keep as is, None is valid
        discord_webhook=admin.discord_webhook
    )
    db.add(dbadmin)
    db.commit()
    db.refresh(dbadmin)
    return dbadmin


def update_admin(db: Session, dbadmin: Admin, modified_admin: AdminModify) -> Admin:
    """
    Updates an admin's details.
    """
    # AdminModify likely has all fields optional or required as per its definition
    # This was from user's code. Assuming AdminModify has hashed_password.
    if modified_admin.password is not None and dbadmin.hashed_password != modified_admin.password:
        dbadmin.hashed_password = modified_admin.password
        dbadmin.password_reset_at = datetime.utcnow()

    # is_sudo is required boolean in AdminModify based on user's original file
    dbadmin.is_sudo = modified_admin.is_sudo

    if modified_admin.telegram_id is not None: # Allow setting to None
        dbadmin.telegram_id = modified_admin.telegram_id

    if modified_admin.discord_webhook is not None: # Allow setting to None
        dbadmin.discord_webhook = modified_admin.discord_webhook

    db.commit()
    db.refresh(dbadmin)
    return dbadmin


def partial_update_admin(db: Session, dbadmin: Admin, modified_admin: AdminPartialModify) -> Admin:
    """
    Partially updates an admin's details. Fields in AdminPartialModify are all Optional.
    """
    update_data = modified_admin.model_dump(exclude_unset=True)

    if "password" in update_data and dbadmin.hashed_password != update_data["password"]:
        dbadmin.hashed_password = update_data["password"]
        dbadmin.password_reset_at = datetime.utcnow()

    for key, value in update_data.items():
        if key != "password" and hasattr(dbadmin, key):
            setattr(dbadmin, key, value)

    db.commit()
    db.refresh(dbadmin)
    return dbadmin


def remove_admin(db: Session, dbadmin: Admin) -> Admin:
    """
    Removes an admin from the database.
    """
    db.delete(dbadmin)
    db.commit()
    return dbadmin


def get_admin_by_id(db: Session, id: int) -> Optional[Admin]: # Can be Optional
    """
    Retrieves an admin by their ID.
    """
    return db.query(Admin).filter(Admin.id == id).first()


def get_admin_by_telegram_id(db: Session, telegram_id: int) -> Optional[Admin]: # Can be Optional
    """
    Retrieves an admin by their Telegram ID.
    """
    return db.query(Admin).filter(Admin.telegram_id == telegram_id).first()


def get_admins(db: Session,
               offset: Optional[int] = None,
               limit: Optional[int] = None,
               username: Optional[str] = None) -> List[Admin]:
    """
    Retrieves a list of admins with optional filters and pagination.
    """
    query = db.query(Admin)
    if username:
        query = query.filter(Admin.username.ilike(f'%{username}%')) # Case-insensitive search
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def reset_admin_usage(db: Session, dbadmin: Admin) -> Admin: # Return type Admin
    """
    Resets an admin's user_usage count and logs the previous usage.
    """
    if dbadmin.users_usage == 0: # No usage to reset
        return dbadmin

    usage_log = AdminUsageLogs(
        admin_id=dbadmin.id, # Set admin_id
        used_traffic_at_reset=dbadmin.users_usage
    )
    db.add(usage_log)
    dbadmin.users_usage = 0

    db.commit()
    db.refresh(dbadmin)
    return dbadmin


def create_user_template(db: Session, user_template: UserTemplateCreate) -> UserTemplate:
    """
    Creates a new user template in the database.
    Note: The `inbounds` logic here assumes UserTemplates still restrict inbounds.
    If templates should also allow all inbounds, this part needs refactoring.
    """
    inbound_tags: List[str] = []
    if user_template.inbounds: # Check if inbounds is provided
        for _, tag_list in user_template.inbounds.items(): # Iterate over protocol: [tags]
            inbound_tags.extend(tag_list)

    db_inbounds_for_template = []
    if inbound_tags: # Only query if there are tags specified
        db_inbounds_for_template = db.query(ProxyInbound).filter(ProxyInbound.tag.in_(inbound_tags)).all()

    dbuser_template = UserTemplate(
        name=user_template.name,
        data_limit=user_template.data_limit if user_template.data_limit is not None else 0,
        expire_duration=user_template.expire_duration if user_template.expire_duration is not None else 0,
        username_prefix=user_template.username_prefix,
        username_suffix=user_template.username_suffix,
        inbounds=db_inbounds_for_template # Assign the fetched ProxyInbound objects
    )
    db.add(dbuser_template)
    db.commit()
    db.refresh(dbuser_template)
    return dbuser_template


def update_user_template(
        db: Session, dbuser_template: UserTemplate, modified_user_template: UserTemplateModify) -> UserTemplate:
    """
    Updates a user template's details.
    Note: The `inbounds` logic here assumes UserTemplates still restrict inbounds.
    """
    update_data = modified_user_template.model_dump(exclude_unset=True, exclude={'inbounds'})

    for key, value in update_data.items():
        if hasattr(dbuser_template, key):
            setattr(dbuser_template, key, value)

    if modified_user_template.inbounds is not None: # If inbounds are part of the modification payload
        inbound_tags: List[str] = []
        for _, tag_list in modified_user_template.inbounds.items():
            inbound_tags.extend(tag_list)

        db_inbounds_for_template = []
        if inbound_tags: # Only query if there are tags specified
            db_inbounds_for_template = db.query(ProxyInbound).filter(ProxyInbound.tag.in_(inbound_tags)).all()
        dbuser_template.inbounds = db_inbounds_for_template # Replace existing inbounds

    db.commit()
    db.refresh(dbuser_template)
    return dbuser_template


def remove_user_template(db: Session, dbuser_template: UserTemplate):
    """
    Removes a user template from the database.
    """
    db.delete(dbuser_template)
    db.commit()


def get_user_template(db: Session, user_template_id: int) -> Optional[UserTemplate]: # Can be Optional
    """
    Retrieves a user template by its ID.
    """
    return db.query(UserTemplate).options(joinedload(UserTemplate.inbounds)).filter(UserTemplate.id == user_template_id).first()


def get_user_templates(
        db: Session, offset: Optional[int] = None, limit: Optional[int] = None) -> List[UserTemplate]:
    """
    Retrieves a list of user templates with optional pagination.
    """
    query = db.query(UserTemplate).options(joinedload(UserTemplate.inbounds)) # Eager load inbounds
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    return query.all()


def get_node(db: Session, name: str) -> Optional[Node]: # node_id was used in the end of file, use name here as per signature
    """
    Retrieves a node by its name.
    """
    return db.query(Node).filter(func.lower(Node.name) == func.lower(name)).first() # Case-insensitive name search


def get_node_by_id(db: Session, node_id: int) -> Optional[Node]:
    """
    Retrieves a node by its ID.
    """
    return db.query(Node).filter(Node.id == node_id).first()


def get_nodes(db: Session,
              status: Optional[Union[NodeStatus, list]] = None,
              enabled: Optional[bool] = None) -> List[Node]: # enabled can be None
    """
    Retrieves nodes based on optional status and enabled filters.
    """
    query = db.query(Node)

    if status:
        if isinstance(status, list):
            query = query.filter(Node.status.in_(status))
        else:
            query = query.filter(Node.status == status)

    if enabled is not None: # Check if enabled filter is applied
        if enabled: # True: only enabled nodes (not disabled)
            query = query.filter(Node.status != NodeStatus.disabled)
        # else: # False: only disabled nodes (if that's the desired interpretation)
            # query = query.filter(Node.status == NodeStatus.disabled)

    return query.all()


def get_nodes_usage(db: Session, start: datetime, end: datetime) -> List[NodeUsageResponse]:
    """
    Retrieves usage data for all nodes within a specified time range.
    """
    usages: Dict[Union[int, None], NodeUsageResponse] = { # type hint for key
        0: NodeUsageResponse(node_id=None, node_name="Master", uplink=0, downlink=0)
    }

    for node in db.query(Node).all():
        usages[node.id] = NodeUsageResponse(
            node_id=node.id,
            node_name=node.name,
            uplink=0,
            downlink=0
        )

    cond = and_(NodeUsage.created_at >= start, NodeUsage.created_at <= end)

    for v in db.query(NodeUsage).filter(cond):
        key_to_use = v.node_id if v.node_id is not None else 0
        if key_to_use in usages:
            usages[key_to_use].uplink += v.uplink
            usages[key_to_use].downlink += v.downlink
        # else:
            # print(f"Warning: Usage logged for unknown node_id {v.node_id} in get_nodes_usage")


    return list(usages.values())


def create_node(db: Session, node: NodeCreate) -> Node:
    """
    Creates a new node in the database.
    """
    dbnode = Node(
        name=node.name,
        address=node.address,
        port=node.port,
        api_port=node.api_port,
        usage_coefficient=node.usage_coefficient # Added from NodeCreate model
    )
    db.add(dbnode)
    db.commit()
    db.refresh(dbnode)
    return dbnode


def remove_node(db: Session, dbnode: Node) -> Node:
    """
    Removes a node from the database.
    """
    db.delete(dbnode)
    db.commit()
    return dbnode


def update_node(db: Session, dbnode: Node, modify: NodeModify) -> Node:
    """
    Updates an existing node with new information.
    """
    update_data = modify.model_dump(exclude_unset=True)
    original_status = dbnode.status

    for key, value in update_data.items():
        if hasattr(dbnode, key):
            setattr(dbnode, key, value)

    # If status is changed to disabled, clear version and message
    if 'status' in update_data and dbnode.status == NodeStatus.disabled:
        dbnode.xray_version = None
        dbnode.message = None
    # If status is changed from disabled to something else (and not just being set), set to connecting
    elif 'status' in update_data and original_status == NodeStatus.disabled and dbnode.status != NodeStatus.disabled:
        dbnode.status = NodeStatus.connecting # Default to connecting when re-enabling
        dbnode.last_status_change = datetime.utcnow() # Also update change time

    if 'status' in update_data and dbnode.status != original_status:
         dbnode.last_status_change = datetime.utcnow()


    db.commit()
    db.refresh(dbnode)
    return dbnode


def update_node_status(db: Session, dbnode: Node, status: NodeStatus, message: Optional[str] = None, version: Optional[str] = None) -> Node:
    """
    Updates the status of a node.
    """
    if dbnode.status != status or dbnode.message != message or dbnode.xray_version != version:
        dbnode.status = status
        dbnode.message = message
        dbnode.xray_version = version
        dbnode.last_status_change = datetime.utcnow()
        db.commit()
        db.refresh(dbnode)
    return dbnode


def create_notification_reminder(
        db: Session, reminder_type: ReminderType, expires_at: datetime, user_id: int, threshold: Optional[int] = None) -> NotificationReminder:
    """
    Creates a new notification reminder.
    """
    reminder = NotificationReminder(
        type=reminder_type,
        expires_at=expires_at,
        user_id=user_id,
        threshold=threshold # threshold can be None
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def get_notification_reminder(
        db: Session, user_id: int, reminder_type: ReminderType, threshold: Optional[int] = None
) -> Optional[NotificationReminder]: # Return type can be Optional
    """
    Retrieves a notification reminder for a user. If expired, it's deleted and None is returned.
    """
    query = db.query(NotificationReminder).filter(
        NotificationReminder.user_id == user_id,
        NotificationReminder.type == reminder_type
    )

    if threshold is not None:
        query = query.filter(NotificationReminder.threshold == threshold)
    # else: # If threshold is None, explicitly filter for reminders where threshold is NULL
    #     query = query.filter(NotificationReminder.threshold.is_(None))


    reminder = query.first()

    if reminder is None:
        return None

    if reminder.expires_at and reminder.expires_at < datetime.utcnow():
        db.delete(reminder)
        db.commit()
        return None

    return reminder


def delete_notification_reminder_by_type(
        db: Session, user_id: int, reminder_type: ReminderType, threshold: Optional[int] = None
) -> None:
    """
    Deletes a notification reminder for a user based on the reminder type and optional threshold.
    """
    stmt = delete(NotificationReminder).where(
        NotificationReminder.user_id == user_id,
        NotificationReminder.type == reminder_type
    )

    if threshold is not None:
        stmt = stmt.where(NotificationReminder.threshold == threshold)
    # else: # If threshold is None, delete reminders of that type where threshold is NULL
    #     stmt = stmt.where(NotificationReminder.threshold.is_(None))


    db.execute(stmt)
    db.commit()


def delete_notification_reminder(db: Session, dbreminder: NotificationReminder) -> None:
    """
    Deletes a specific notification reminder.
    """
    db.delete(dbreminder)
    db.commit()
    # No return needed


def count_online_users(db: Session, hours: int = 24) -> int:
    """Counts users who were online in the last N hours."""
    time_threshold = datetime.utcnow() - timedelta(hours=hours)
    query = db.query(func.count(User.id)).filter(
        User.online_at.isnot(None),
        User.online_at >= time_threshold
    )
    count = query.scalar() # Use scalar() instead of scalar_one_or_none
    return count if count is not None else 0

