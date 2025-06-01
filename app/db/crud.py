"""
Functions for managing proxy hosts, users, user templates, nodes, and administrative tasks.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union
from .models import TLS

from sqlalchemy import and_, delete, func, or_, select  # Add select here
from sqlalchemy.orm import Query, Session, joinedload
from sqlalchemy.sql.functions import coalesce

from app import logger  # Add logger import

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
    ProxyHost as DBProxyHost, # Renamed to avoid conflict with Pydantic model
    ProxyInbound,
    System,
    User as DBUser, # Renamed to avoid conflict with Pydantic model
    UserTemplate,
    UserUsageResetLogs,
)
from app.models.admin import AdminCreate, AdminModify, AdminPartialModify
from app.models.node import NodeCreate, NodeModify, NodeStatus, NodeUsageResponse
from app.models.proxy import ProxyHost as ProxyHostModify # Pydantic model
from app.models.proxy import ProxyTypes
from app.models.user import (
    ReminderType,
    UserCreate,
    UserDataLimitResetStrategy,
    UserModify,
    UserResponse,
    UserStatus,
    UserUsageResponse
)
from app.models.user_template import UserTemplateCreate, UserTemplateModify
from app.utils.helpers import calculate_expiration_days, calculate_usage_percent
from config import NOTIFY_DAYS_LEFT, NOTIFY_REACHED_USAGE_PERCENT, USERS_AUTODELETE_DAYS
import logging


# Set logging level to DEBUG
logger.setLevel(logging.DEBUG)


def add_default_host(db: Session, inbound: ProxyInbound):
    """
    Adds a default host to a proxy inbound.

    Args:
        db (Session): Database session.
        inbound (ProxyInbound): Proxy inbound to add the default host to.
    """
    host = DBProxyHost(remark="🚀 Marz ({USERNAME}) [{PROTOCOL} - {TRANSPORT}]", address="{SERVER_IP}", inbound=inbound)
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


def get_hosts(db: Session, inbound_tag: str) -> List[DBProxyHost]:
    """
    Retrieves hosts for a given inbound tag.
    Note: For the new model, you'll likely use get_proxy_hosts_by_node_id more often.

    Args:
        db (Session): Database session.
        inbound_tag (str): The tag of the inbound.

    Returns:
        List[DBProxyHost]: List of hosts for the inbound.
    """
    inbound = get_or_create_inbound(db, inbound_tag)
    return inbound.hosts


def add_host(db: Session, inbound_tag: str, host_data: ProxyHostModify, node_id: Optional[int] = None) -> List[DBProxyHost]:
    """
    Adds a new host to a proxy inbound, optionally associating it with a node.

    Args:
        db (Session): Database session.
        inbound_tag (str): The tag of the inbound.
        host_data (ProxyHostModify): Host details to be added (Pydantic model).
        node_id (Optional[int]): The ID of the node this host is associated with.


    Returns:
        List[DBProxyHost]: Updated list of hosts for the inbound.
    """
    inbound = get_or_create_inbound(db, inbound_tag)
    new_db_host = DBProxyHost(
            remark=host_data.remark,
            address=host_data.address,
            port=host_data.port,
            path=host_data.path,
            sni=host_data.sni,
            host=host_data.host,
            inbound_tag=inbound.tag, # Set inbound_tag directly
            node_id=node_id, # Associate with a node
            security=host_data.security,
            alpn=host_data.alpn,
            fingerprint=host_data.fingerprint,
            allowinsecure=host_data.allowinsecure,
            is_disabled=host_data.is_disabled,
            mux_enable=host_data.mux_enable,
            fragment_setting=host_data.fragment_setting,
            noise_setting=host_data.noise_setting,
            random_user_agent=host_data.random_user_agent,
            use_sni_as_host=host_data.use_sni_as_host
        )
    # inbound.hosts.append(new_db_host) # Adding directly to session is fine
    db.add(new_db_host)
    db.commit()
    db.refresh(inbound) # Refresh inbound to reflect new host in its collection if needed by caller
    return inbound.hosts


def update_hosts(db: Session, inbound_tag: str, modified_hosts_data: List[ProxyHostModify]) -> List[DBProxyHost]:
    """
    Updates hosts for a given inbound tag. This replaces all existing hosts for the inbound.
    NOTE: This function replaces ALL hosts for an inbound_tag. If hosts can be associated with different nodes
    but share an inbound_tag, this wholesale replacement might be too broad. Consider if you need
    to update hosts on a per-node basis for a given inbound_tag instead.

    Args:
        db (Session): Database session.
        inbound_tag (str): The tag of the inbound.
        modified_hosts_data (List[ProxyHostModify]): List of modified hosts (Pydantic models).

    Returns:
        List[DBProxyHost]: Updated list of hosts for the inbound.
    """
    inbound = get_or_create_inbound(db, inbound_tag)

    # Delete existing hosts for this specific inbound tag
    db.query(DBProxyHost).filter(DBProxyHost.inbound_tag == inbound_tag).delete(synchronize_session=False)
    db.flush()

    new_host_objects = []
    for host_data in modified_hosts_data:
        new_db_host = DBProxyHost(
            remark=host_data.remark,
            address=host_data.address,
            port=host_data.port,
            path=host_data.path,
            sni=host_data.sni,
            host=host_data.host,
            inbound_tag=inbound.tag,
            node_id=host_data.node_id, # Assuming ProxyHostModify Pydantic model now includes node_id
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

    db.add_all(new_host_objects)
    db.commit()
    db.refresh(inbound)
    return inbound.hosts


def get_user_queryset(db: Session) -> Query:
    return db.query(DBUser).options(
        joinedload(DBUser.admin),
        joinedload(DBUser.next_plan),
        joinedload(DBUser.proxies),
        joinedload(DBUser.usage_logs),
        joinedload(DBUser.active_node) # Eager load the active_node
    )


def get_user(db: Session, account_number: str) -> Optional[DBUser]:
    account_number_to_query = account_number.lower()
    return get_user_queryset(db).filter(DBUser.account_number == account_number_to_query).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[DBUser]:
    return get_user_queryset(db).filter(DBUser.id == user_id).first()

def get_user_by_sub_token(db: Session, token: str) -> Optional[DBUser]: # Added for subscription
    # Assuming token is the account_number for subscriptions
    return get_user(db, token)


class UsersSortingOptionsEnum(Enum): # Changed to class for better type hinting if needed
    account_number_asc = DBUser.account_number.asc()
    used_traffic_asc = DBUser.used_traffic.asc()
    data_limit_asc = DBUser.data_limit.asc()
    expire_asc = DBUser.expire.asc()
    created_at_asc = DBUser.created_at.asc()
    account_number_desc = DBUser.account_number.desc()
    used_traffic_desc = DBUser.used_traffic.desc()
    data_limit_desc = DBUser.data_limit.desc()
    expire_desc = DBUser.expire.desc()
    created_at_desc = DBUser.created_at.desc()

    @classmethod
    def from_string(cls, s: str) -> Optional['UsersSortingOptionsEnum']:
        try:
            if s.startswith("-"):
                return cls[s[1:] + "_desc"]
            else:
                return cls[s + "_asc"]
        except KeyError:
            return None


def get_users(db: Session,
              offset: Optional[int] = None,
              limit: Optional[int] = None,
              account_numbers: Optional[List[str]] = None,
              search: Optional[str] = None,
              status: Optional[Union[UserStatus, list]] = None,
              sort: Optional[List[UsersSortingOptionsEnum]] = None, # Use the class
              admins: Optional[List[str]] = None, # List of admin usernames for filtering
              reset_strategy: Optional[Union[UserDataLimitResetStrategy, list]] = None,
              return_with_count: bool = False) -> Union[List[DBUser], Tuple[List[DBUser], int]]:
    query = get_user_queryset(db)

    if account_numbers:
        lowercase_account_numbers = [acc_num.lower() for acc_num in account_numbers]
        query = query.filter(DBUser.account_number.in_(lowercase_account_numbers))

    if search:
        search_term = f"%{search.lower()}%"
        query = query.filter(
            or_(
                DBUser.account_number.ilike(search_term),
                DBUser.note.ilike(search_term)
            )
        )

    if status:
        if isinstance(status, list):
            query = query.filter(DBUser.status.in_(status))
        else:
            query = query.filter(DBUser.status == status)

    if reset_strategy:
        if isinstance(reset_strategy, list):
            query = query.filter(DBUser.data_limit_reset_strategy.in_(reset_strategy))
        else:
            query = query.filter(DBUser.data_limit_reset_strategy == reset_strategy)

    if admins:
        query = query.join(DBUser.admin).filter(Admin.username.in_(admins))

    count_query = query.with_session(db) # Create a new query for count based on current filters

    if sort:
        # Convert string sort options to enum values if they are passed as strings
        processed_sort_options = []
        for opt_val in sort:
            if isinstance(opt_val, str):
                enum_opt = UsersSortingOptionsEnum.from_string(opt_val)
                if enum_opt:
                    processed_sort_options.append(enum_opt.value)
            elif isinstance(opt_val, UsersSortingOptionsEnum):
                 processed_sort_options.append(opt_val.value)

        if processed_sort_options:
            query = query.order_by(*processed_sort_options)
        else: # Default sort if provided sort strings are invalid
            query = query.order_by(DBUser.id.desc())
    else: # Default sort
        query = query.order_by(DBUser.id.desc())


    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    if return_with_count:
        # For an accurate count with joins and potential duplicates before distinct User.id
        total_count = count_query.distinct(DBUser.id).count()
        return query.all(), total_count

    return query.all()


def get_user_usages(db: Session, dbuser: DBUser, start: datetime, end: datetime) -> List[UserUsageResponse]:
    usages: Dict[Union[int, None], UserUsageResponse] = {
        None: UserUsageResponse( # Use None as key for Master/Core
            node_id=None,
            node_name="Master", # Or however you identify core traffic not on a specific node
            used_traffic=0
        )
    }

    for node in db.query(Node).all(): # Pre-populate with all known nodes
        usages[node.id] = UserUsageResponse(
            node_id=node.id,
            node_name=node.name,
            used_traffic=0
        )

    cond = and_(NodeUserUsage.user_id == dbuser.id,
                NodeUserUsage.created_at >= start,
                NodeUserUsage.created_at <= end)

    for v in db.query(NodeUserUsage).filter(cond):
        # v.node_id can be None for traffic not associated with a specific slave node
        key_to_use = v.node_id # This will be None or an int
        if key_to_use in usages:
            usages[key_to_use].used_traffic += v.used_traffic
        else:
            # This case implies usage was logged for a node_id that doesn't exist in Node table
            # or wasn't pre-populated. Could create an entry on the fly or log.
            logger.warning(f"Usage logged for user {dbuser.id} on unknown or unexpected node_id {v.node_id}. Creating ad-hoc entry.")
            # To handle this gracefully, you might fetch node name if it's a new valid node_id
            # For now, let's assume it should have been in `usages`
            usages[key_to_use] = UserUsageResponse(node_id=v.node_id, node_name=f"Unknown Node {v.node_id}", used_traffic=v.used_traffic)


    return list(usages.values())


def get_users_count(db: Session, status: Optional[UserStatus] = None, admin: Optional[Admin] = None) -> int:
    query = db.query(func.count(DBUser.id))
    if admin:
        query = query.join(DBUser.admin).filter(Admin.id == admin.id) # Filter by Admin object's ID
    if status:
        query = query.filter(DBUser.status == status)
    count = query.scalar()
    return count if count is not None else 0


def create_user(db: Session, account_number: str, user: UserCreate, admin: Optional[Admin] = None) -> DBUser:

    proxies_list = []
    if user.proxies: # Ensure proxies is not None
        for proxy_type_enum, settings_model in user.proxies.items():
            # Convert settings to dict. Pydantic's model_dump handles enum serialization.
            settings_dict = settings_model.model_dump(exclude_none=True)
            proxies_list.append(
                Proxy(
                    type=proxy_type_enum,
                    settings=settings_dict
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

    dbuser = DBUser(
        account_number=account_number.lower(),
        proxies=proxies_list,
        status=user.status if user.status is not None else UserStatus.disabled, # Default status
        data_limit=user.data_limit,
        expire=user.expire,
        admin_id=admin.id if admin else None,
        data_limit_reset_strategy=user.data_limit_reset_strategy,
        note=user.note,
        on_hold_expire_duration=user.on_hold_expire_duration,
        on_hold_timeout=user.on_hold_timeout,
        auto_delete_in_days=user.auto_delete_in_days,
        next_plan=next_plan_orm,
        active_node_id=None # New users don't have an active node
    )
    db.add(dbuser)
    db.commit()
    db.refresh(dbuser)
    print(f"[DEBUG] create_user: User created successfully with ID {dbuser.id}")
    return get_user_by_id(db, dbuser.id) or dbuser # Re-fetch to ensure all relations are loaded


def remove_user(db: Session, dbuser: DBUser) -> DBUser:
    db.delete(dbuser)
    db.commit()
    return dbuser


def remove_users(db: Session, dbusers: List[DBUser]):
    for dbuser_obj in dbusers: # Renamed to avoid conflict
        db.delete(dbuser_obj)
    db.commit()


def update_user(db: Session, dbuser: DBUser, modify: UserModify) -> DBUser:
    print(f"[DEBUG] update_user: Starting update for user {dbuser.account_number}")
    print(f"[DEBUG] update_user: Current user state: {dbuser.__dict__}")
    print(f"[DEBUG] update_user: Modify data: {modify.model_dump()}")

    if modify.proxies is not None:
        print(f"[DEBUG] update_user: Updating proxies")
        # Clear existing proxies for this user
        for p in list(dbuser.proxies): # Iterate over a copy
            print(f"[DEBUG] update_user: Removing proxy {p.type}")
            db.delete(p)
        dbuser.proxies.clear() # Clear the collection
        db.flush() # Process deletes

        # Add new/updated proxies from modify payload
        for proxy_type_enum, settings_model in modify.proxies.items():
            print(f"[DEBUG] update_user: Adding proxy type {proxy_type_enum}")
            dbuser.proxies.append(
                Proxy(type=proxy_type_enum, settings=settings_model.model_dump(exclude_none=True))
            )

    update_data = modify.model_dump(exclude_unset=True, exclude={'proxies', 'active_node_id'})
    print(f"[DEBUG] update_user: Update data after processing: {update_data}")
    original_status = dbuser.status

    for key, value in update_data.items():
        print(f"[DEBUG] update_user: Processing field {key} with value {value}")
        if key == "next_plan":
            if value is None:
                if dbuser.next_plan:
                    print(f"[DEBUG] update_user: Removing next plan")
                    db.delete(dbuser.next_plan)
                    dbuser.next_plan = None
            else:
                if dbuser.next_plan:
                    print(f"[DEBUG] update_user: Updating existing next plan")
                    for np_key, np_value in value.items():
                        setattr(dbuser.next_plan, np_key, np_value)
                else:
                    print(f"[DEBUG] update_user: Creating new next plan")
                    dbuser.next_plan = NextPlan(**value, user_id=dbuser.id)
        elif hasattr(dbuser, key):
            print(f"[DEBUG] update_user: Setting {key} to {value}")
            setattr(dbuser, key, value)

    # Status change side effects
    if 'status' in update_data and dbuser.status != original_status:
        print(f"[DEBUG] update_user: Status changed from {original_status} to {dbuser.status}")
        dbuser.last_status_change = datetime.utcnow()

    # Data limit change side effects
    if 'data_limit' in update_data:
        value = update_data['data_limit']
        print(f"[DEBUG] update_user: Processing data limit change to {value}")
        if dbuser.status not in (UserStatus.expired, UserStatus.disabled):
            if not value or (dbuser.used_traffic < value if value is not None else True):
                if dbuser.status == UserStatus.limited and dbuser.status != UserStatus.on_hold:
                    print(f"[DEBUG] update_user: Setting status to active due to data limit change")
                    setattr(dbuser, 'status', UserStatus.active)
                    dbuser.last_status_change = datetime.utcnow()
            elif value is not None and dbuser.used_traffic >= value:
                print(f"[DEBUG] update_user: Setting status to limited due to data limit change")
                setattr(dbuser, 'status', UserStatus.limited)
                dbuser.last_status_change = datetime.utcnow()

    # Expire change side effects
    if 'expire' in update_data:
        value = update_data['expire']
        print(f"[DEBUG] update_user: Processing expire change to {value}")
        if dbuser.status in (UserStatus.active, UserStatus.expired, UserStatus.limited):
            if not value or (datetime.fromtimestamp(value) > datetime.utcnow() if value is not None else True):
                if dbuser.status == UserStatus.expired:
                    print(f"[DEBUG] update_user: Setting status to active due to expire change")
                    setattr(dbuser, 'status', UserStatus.active)
                    dbuser.last_status_change = datetime.utcnow()
            elif value is not None and datetime.fromtimestamp(value) <= datetime.utcnow():
                print(f"[DEBUG] update_user: Setting status to expired due to expire change")
                setattr(dbuser, 'status', UserStatus.expired)
                dbuser.last_status_change = datetime.utcnow()

    print(f"[DEBUG] update_user: Committing changes")
    dbuser.edit_at = datetime.utcnow()
    db.commit()
    print(f"[DEBUG] update_user: Refreshing user object")
    db.refresh(dbuser)
    print(f"[DEBUG] update_user: Update complete for user {dbuser.account_number}")
    return get_user_by_id(db, dbuser.id) or dbuser


def reset_user_data_usage(db: Session, dbuser: DBUser) -> DBUser:
    usage_log = UserUsageResetLogs(user_id=dbuser.id, used_traffic_at_reset=dbuser.used_traffic)
    db.add(usage_log)
    dbuser.used_traffic = 0
    db.query(NodeUserUsage).filter(NodeUserUsage.user_id == dbuser.id).delete(synchronize_session=False)

    if dbuser.status not in (UserStatus.expired, UserStatus.disabled, UserStatus.on_hold):
        if dbuser.data_limit is None or dbuser.data_limit > 0:
            dbuser.status = UserStatus.active
            dbuser.last_status_change = datetime.utcnow()

    if dbuser.next_plan:
        db.delete(dbuser.next_plan)
        dbuser.next_plan = None

    db.commit()
    db.refresh(dbuser)
    return get_user_by_id(db, dbuser.id) or dbuser


def reset_user_by_next(db: Session, dbuser: DBUser) -> DBUser:
    if dbuser.next_plan is None: return dbuser

    usage_log = UserUsageResetLogs(user_id=dbuser.id, used_traffic_at_reset=dbuser.used_traffic)
    db.add(usage_log)
    db.query(NodeUserUsage).filter(NodeUserUsage.user_id == dbuser.id).delete(synchronize_session=False)

    remaining_traffic = 0
    if dbuser.next_plan.add_remaining_traffic and dbuser.data_limit is not None:
        remaining_traffic = max(0, dbuser.data_limit - dbuser.used_traffic)

    dbuser.data_limit = (dbuser.next_plan.data_limit + remaining_traffic) if dbuser.next_plan.data_limit is not None else None
    dbuser.expire = dbuser.next_plan.expire
    dbuser.used_traffic = 0
    dbuser.status = UserStatus.active
    dbuser.last_status_change = datetime.utcnow()

    db.delete(dbuser.next_plan)
    dbuser.next_plan = None
    db.commit()
    db.refresh(dbuser)
    return get_user_by_id(db, dbuser.id) or dbuser


def revoke_user_sub(db: Session, dbuser: DBUser) -> DBUser:
    dbuser.sub_revoked_at = datetime.utcnow()

    # Re-fetch with eager loaded proxies to ensure UserResponse has them for revoke()
    # If dbuser comes from get_validated_user, it should already have them via get_user_queryset
    # If not, an explicit re-fetch or ensuring proxies are loaded is crucial here.
    # For safety, let's assume dbuser might be detached or proxies not loaded by caller:
    user_with_proxies = get_user_by_id(db, dbuser.id)
    if not user_with_proxies: return dbuser # Should not happen if dbuser is valid

    user_pydantic = UserResponse.model_validate(user_with_proxies)

    new_proxy_settings_list = []
    if user_pydantic.proxies: # Check if proxies is not None
        for proxy_type, pydantic_proxy_settings in user_pydantic.proxies.items():
            if hasattr(pydantic_proxy_settings, 'revoke'): # Ensure method exists
                pydantic_proxy_settings.revoke()
            new_proxy_settings_list.append({
                "type": proxy_type,
                "settings": pydantic_proxy_settings.model_dump(exclude_none=True)
            })

    # Update proxies in the database
    for p in list(user_with_proxies.proxies): db.delete(p) # Use user_with_proxies
    user_with_proxies.proxies.clear()
    db.flush()

    for new_proxy_data in new_proxy_settings_list:
        user_with_proxies.proxies.append(
            Proxy(type=new_proxy_data["type"], settings=new_proxy_data["settings"])
        )

    # Update the original dbuser object's fields if it's a different instance
    if dbuser.id == user_with_proxies.id:
        dbuser.sub_revoked_at = user_with_proxies.sub_revoked_at # Sync this field

    db.commit()
    db.refresh(user_with_proxies) # Refresh the instance that had proxies modified
    return get_user_by_id(db, user_with_proxies.id) or user_with_proxies # Re-fetch fully


def update_user_sub(db: Session, dbuser: DBUser, user_agent: str) -> DBUser:
    dbuser.sub_updated_at = datetime.utcnow()
    dbuser.sub_last_user_agent = user_agent
    db.commit()
    db.refresh(dbuser)
    return dbuser


def reset_all_users_data_usage(db: Session, admin: Optional[Admin] = None):
    query = get_user_queryset(db) # Use queryset for potential eager loads if status logic becomes complex
    if admin:
        query = query.join(DBUser.admin).filter(Admin.id == admin.id) # Correctly filter by Admin object

    for user_item in query.all(): # Renamed var
        user_item.used_traffic = 0
        db.query(NodeUserUsage).filter(NodeUserUsage.user_id == user_item.id).delete(synchronize_session=False)
        if user_item.status not in [UserStatus.on_hold, UserStatus.expired, UserStatus.disabled]:
            user_item.status = UserStatus.active
            user_item.last_status_change = datetime.utcnow() # Update if status changed
        if user_item.next_plan:
            db.delete(user_item.next_plan)
            user_item.next_plan = None
    db.commit()


def disable_all_active_users(db: Session, admin: Optional[Admin] = None):
    query = db.query(DBUser).filter(DBUser.status.in_([UserStatus.active, UserStatus.on_hold]))
    if admin:
        query = query.join(DBUser.admin).filter(Admin.id == admin.id)
    query.update(
        {DBUser.status: UserStatus.disabled, DBUser.last_status_change: datetime.utcnow()},
        synchronize_session=False
    )
    db.commit()


def activate_all_disabled_users(db: Session, admin: Optional[Admin] = None):
    on_hold_criteria_users_query = db.query(DBUser).filter(
        DBUser.status == UserStatus.disabled,
        DBUser.on_hold_expire_duration.isnot(None),
        DBUser.on_hold_timeout.isnot(None),
    )
    active_criteria_users_query = db.query(DBUser).filter(DBUser.status == UserStatus.disabled)

    if admin:
        on_hold_criteria_users_query = on_hold_criteria_users_query.join(DBUser.admin).filter(Admin.id == admin.id)
        active_criteria_users_query = active_criteria_users_query.join(DBUser.admin).filter(Admin.id == admin.id)

        on_hold_user_ids = [u.id for u in on_hold_criteria_users_query.with_session(db).all()] # Ensure session
        if on_hold_user_ids: # type: ignore
            active_criteria_users_query = active_criteria_users_query.filter(DBUser.id.notin_(on_hold_user_ids)) # type: ignore

    on_hold_criteria_users_query.update(
        {DBUser.status: UserStatus.on_hold, DBUser.last_status_change: datetime.utcnow()},
        synchronize_session=False
    )
    active_criteria_users_query.update(
        {DBUser.status: UserStatus.active, DBUser.last_status_change: datetime.utcnow()},
        synchronize_session=False
    )
    db.commit()


def autodelete_expired_users(db: Session, include_limited_users: bool = False) -> List[DBUser]:
    target_status = [UserStatus.expired]
    if include_limited_users:
        target_status.append(UserStatus.limited)

    effective_auto_delete_days = coalesce(DBUser.auto_delete_in_days, USERS_AUTODELETE_DAYS) # type: ignore
    query = db.query(DBUser, effective_auto_delete_days.label("effective_days")) \
              .filter(effective_auto_delete_days >= 0) \
              .filter(DBUser.status.in_(target_status)) \
              .options(joinedload(DBUser.admin))

    users_to_delete_list = [] # Renamed variable
    for user_obj, auto_delete_val in query.all(): # Renamed variable
        if user_obj.last_status_change and (user_obj.last_status_change + timedelta(days=auto_delete_val)) <= datetime.utcnow():
            users_to_delete_list.append(user_obj)

    if users_to_delete_list:
        # Deactivation from XRay should be handled by the caller job (e.g., remove_expired_users job)
        # by iterating `users_to_delete_list` and calling `xray.operations.deactivate_user_from_active_node`
        # *before* calling this `remove_users`.
        # This CRUD function focuses on DB deletion.
        remove_users(db, users_to_delete_list)
    return users_to_delete_list


def get_all_users_usages(
        db: Session, admin_usernames: Optional[List[str]], start: datetime, end: datetime # Changed param name for clarity
) -> List[UserUsageResponse]:
    usages: Dict[Union[int, None], UserUsageResponse] = {
        None: UserUsageResponse(node_id=None, node_name="Master", used_traffic=0)
    }
    for node_obj in db.query(Node).all(): # Renamed var
        usages[node_obj.id] = UserUsageResponse(node_id=node_obj.id, node_name=node_obj.name, used_traffic=0)

    usage_query_conditions = [
        NodeUserUsage.created_at >= start,
        NodeUserUsage.created_at <= end
    ]
    if admin_usernames: # If a list of admin usernames is provided
        admin_ids_subquery = db.query(Admin.id).filter(Admin.username.in_(admin_usernames)).subquery()
        user_ids_subquery = db.query(DBUser.id).filter(DBUser.admin_id.in_(admin_ids_subquery)).subquery()
        usage_query_conditions.append(NodeUserUsage.user_id.in_(user_ids_subquery)) # type: ignore

    for v_usage in db.query(NodeUserUsage).filter(and_(*usage_query_conditions)): # Renamed var
        key_to_use = v_usage.node_id
        if key_to_use in usages:
            usages[key_to_use].used_traffic += v_usage.used_traffic
        else:
            logger.warning(f"Usage found for unexpected node_id: {v_usage.node_id} in get_all_users_usages")
            usages[key_to_use] = UserUsageResponse(node_id=v_usage.node_id, node_name=f"Unknown Node {v_usage.node_id}", used_traffic=v_usage.used_traffic)


    return list(usages.values())


def update_user_status(db: Session, dbuser: DBUser, status: UserStatus) -> DBUser:
    if dbuser.status != status:
        dbuser.status = status
        dbuser.last_status_change = datetime.utcnow()
        # If status change implies XRay deactivation (e.g., to disabled/expired)
        # and user has an active node, this should be handled by xray.operations.update_user.
        # This CRUD is just for DB state.
        # if status not in [UserStatus.active, UserStatus.on_hold] and dbuser.active_node_id is not None:
        #     dbuser.active_node_id = None # Potentially clear active node if status becomes inactive
        db.commit()
        db.refresh(dbuser)
    return dbuser


def set_owner(db: Session, dbuser: DBUser, admin: Admin) -> DBUser:
    dbuser.admin_id = admin.id
    db.commit()
    db.refresh(dbuser)
    return get_user_by_id(db, dbuser.id) or dbuser


def start_user_expire(db: Session, dbuser: DBUser) -> DBUser:
    if dbuser.on_hold_expire_duration is not None:
        expire_timestamp = int(datetime.utcnow().timestamp()) + dbuser.on_hold_expire_duration
        dbuser.expire = expire_timestamp
        dbuser.on_hold_expire_duration = None
        dbuser.on_hold_timeout = None
        if dbuser.status == UserStatus.on_hold:
            dbuser.status = UserStatus.active
            dbuser.last_status_change = datetime.utcnow()
        db.commit()
        db.refresh(dbuser)
    return dbuser

# --- System, JWT, TLS --- (Largely unchanged unless related to new model)
def get_system_usage(db: Session) -> Optional[System]:
    return db.query(System).first()

def get_jwt_secret_key(db: Session) -> Optional[str]:
    jwt_record = db.query(JWT).first()
    return jwt_record.secret_key if jwt_record else None

def get_tls_certificate(db: Session) -> Optional[TLS]:
    return db.query(TLS).first()

# --- Admin --- (Largely unchanged unless related to new user model interactions)
def get_admin(db: Session, username: str) -> Optional[Admin]:
    return db.query(Admin).filter(func.lower(Admin.username) == func.lower(username)).first() # Case-insensitive

def create_admin(db: Session, admin_data: AdminCreate) -> Admin: # Renamed param
    dbadmin = Admin(
        username=admin_data.username,
        hashed_password=admin_data.password, # Assuming AdminCreate.password is already hashed
        is_sudo=admin_data.is_sudo if admin_data.is_sudo is not None else False,
        telegram_id=admin_data.telegram_id,
        discord_webhook=admin_data.discord_webhook
    )
    db.add(dbadmin)
    db.commit()
    db.refresh(dbadmin)
    return dbadmin

def update_admin(db: Session, dbadmin: Admin, modified_admin_data: AdminModify) -> Admin: # Renamed param
    if modified_admin_data.password is not None and dbadmin.hashed_password != modified_admin_data.password:
        dbadmin.hashed_password = modified_admin_data.password # Assuming already hashed
        dbadmin.password_reset_at = datetime.utcnow()

    dbadmin.is_sudo = modified_admin_data.is_sudo # is_sudo is required in AdminModify

    # Allow clearing telegram_id and discord_webhook by passing None
    dbadmin.telegram_id = modified_admin_data.telegram_id
    dbadmin.discord_webhook = modified_admin_data.discord_webhook

    db.commit()
    db.refresh(dbadmin)
    return dbadmin

def partial_update_admin(db: Session, dbadmin: Admin, modified_admin_data: AdminPartialModify) -> Admin: # Renamed param
    update_data = modified_admin_data.model_dump(exclude_unset=True)
    if "password" in update_data and dbadmin.hashed_password != update_data["password"]:
        dbadmin.hashed_password = update_data["password"] # Assuming already hashed
        dbadmin.password_reset_at = datetime.utcnow()
    for key, value in update_data.items():
        if key != "password" and hasattr(dbadmin, key):
            setattr(dbadmin, key, value)
    db.commit()
    db.refresh(dbadmin)
    return dbadmin

def remove_admin(db: Session, dbadmin: Admin) -> Admin:
    db.delete(dbadmin)
    db.commit()
    return dbadmin

def get_admin_by_id(db: Session, admin_id: int) -> Optional[Admin]: # Renamed param
    return db.query(Admin).filter(Admin.id == admin_id).first()

def get_admin_by_telegram_id(db: Session, telegram_id: int) -> Optional[Admin]:
    return db.query(Admin).filter(Admin.telegram_id == telegram_id).first()

def get_admins(db: Session, offset: Optional[int] = None, limit: Optional[int] = None, username: Optional[str] = None) -> List[Admin]:
    query = db.query(Admin)
    if username:
        query = query.filter(Admin.username.ilike(f'%{username}%'))
    if offset is not None: query = query.offset(offset)
    if limit is not None: query = query.limit(limit)
    return query.all()

def reset_admin_usage(db: Session, dbadmin: Admin) -> Admin:
    if dbadmin.users_usage == 0: return dbadmin
    usage_log = AdminUsageLogs(admin_id=dbadmin.id, used_traffic_at_reset=dbadmin.users_usage)
    db.add(usage_log)
    dbadmin.users_usage = 0
    db.commit()
    db.refresh(dbadmin)
    return dbadmin

# --- User Template --- (Largely unchanged)
def create_user_template(db: Session, user_template_data: UserTemplateCreate) -> UserTemplate: # Renamed param
    inbound_tags_list: List[str] = [] # Renamed param
    if user_template_data.inbounds:
        for _, tag_list_val in user_template_data.inbounds.items(): # Renamed param
            inbound_tags_list.extend(tag_list_val)

    db_inbounds_for_template_list = [] # Renamed param
    if inbound_tags_list:
        db_inbounds_for_template_list = db.query(ProxyInbound).filter(ProxyInbound.tag.in_(inbound_tags_list)).all()

    dbuser_template_obj = UserTemplate( # Renamed param
        name=user_template_data.name,
        data_limit=user_template_data.data_limit if user_template_data.data_limit is not None else 0,
        expire_duration=user_template_data.expire_duration if user_template_data.expire_duration is not None else 0,
        username_prefix=user_template_data.username_prefix,
        username_suffix=user_template_data.username_suffix,
        inbounds=db_inbounds_for_template_list
    )
    db.add(dbuser_template_obj)
    db.commit()
    db.refresh(dbuser_template_obj)
    return dbuser_template_obj

def update_user_template(db: Session, dbuser_template_obj: UserTemplate, modified_user_template_data: UserTemplateModify) -> UserTemplate: # Renamed params
    update_data = modified_user_template_data.model_dump(exclude_unset=True, exclude={'inbounds'})
    for key, value in update_data.items():
        if hasattr(dbuser_template_obj, key): setattr(dbuser_template_obj, key, value)

    if modified_user_template_data.inbounds is not None:
        inbound_tags_list: List[str] = [] # Renamed
        for _, tag_list_val in modified_user_template_data.inbounds.items(): # Renamed
            inbound_tags_list.extend(tag_list_val)

        db_inbounds_for_template_list = [] # Renamed
        if inbound_tags_list:
            db_inbounds_for_template_list = db.query(ProxyInbound).filter(ProxyInbound.tag.in_(inbound_tags_list)).all()
        dbuser_template_obj.inbounds = db_inbounds_for_template_list

    db.commit()
    db.refresh(dbuser_template_obj)
    return dbuser_template_obj

def remove_user_template(db: Session, dbuser_template_obj: UserTemplate): # Renamed param
    db.delete(dbuser_template_obj)
    db.commit()

def get_user_template(db: Session, user_template_id: int) -> Optional[UserTemplate]:
    return db.query(UserTemplate).options(joinedload(UserTemplate.inbounds)).filter(UserTemplate.id == user_template_id).first()

def get_user_templates(db: Session, offset: Optional[int] = None, limit: Optional[int] = None) -> List[UserTemplate]:
    query = db.query(UserTemplate).options(joinedload(UserTemplate.inbounds))
    if offset is not None: query = query.offset(offset)
    if limit is not None: query = query.limit(limit)
    return query.all()

# --- Node --- (Largely unchanged regarding direct user linking in these CRUDs)
def get_node(db: Session, name: str) -> Optional[Node]:
    return db.query(Node).filter(func.lower(Node.name) == func.lower(name)).first()

def get_node_by_id(db: Session, node_id: int) -> Optional[Node]:
    return db.query(Node).filter(Node.id == node_id).first()

def get_nodes(db: Session, status: Optional[Union[NodeStatus, list]] = None, enabled: Optional[bool] = None) -> List[Node]:
    query = db.query(Node)
    if status:
        if isinstance(status, list): query = query.filter(Node.status.in_(status))
        else: query = query.filter(Node.status == status)
    if enabled is not None:
        if enabled: query = query.filter(Node.status != NodeStatus.disabled)
        # else: query = query.filter(Node.status == NodeStatus.disabled) # Only if explicit "show only disabled" is needed
    return query.all()

def get_nodes_usage(db: Session, start: datetime, end: datetime) -> List[NodeUsageResponse]:
    usages: Dict[Union[int, None], NodeUsageResponse] = {
        None: NodeUsageResponse(node_id=None, node_name="Master", uplink=0, downlink=0)
    }
    for node_obj in db.query(Node).all(): # Renamed var
        usages[node_obj.id] = NodeUsageResponse(node_id=node_obj.id, node_name=node_obj.name, uplink=0, downlink=0)

    cond = and_(NodeUsage.created_at >= start, NodeUsage.created_at <= end)
    for v_usage in db.query(NodeUsage).filter(cond): # Renamed var
        key_to_use = v_usage.node_id
        if key_to_use in usages:
            usages[key_to_use].uplink += v_usage.uplink
            usages[key_to_use].downlink += v_usage.downlink
        else:
            logger.warning(f"Usage found for unexpected node_id: {v_usage.node_id} in get_nodes_usage")
            usages[key_to_use] = NodeUsageResponse(node_id=v_usage.node_id, node_name=f"Unknown Node {v_usage.node_id}", uplink=v_usage.uplink, downlink=v_usage.downlink)

    return list(usages.values())

def create_node(db: Session, node_data: NodeCreate) -> Node: # Renamed param
    dbnode = Node(
        name=node_data.name,
        address=node_data.address,
        port=node_data.port,
        api_port=node_data.api_port,
        usage_coefficient=node_data.usage_coefficient,
        panel_client_cert_pem=node_data.panel_client_cert_pem,
        panel_client_key_pem=node_data.panel_client_key_pem
    )
    db.add(dbnode)
    db.commit()
    db.refresh(dbnode)
    return dbnode

def remove_node(db: Session, dbnode_obj: Node) -> Node: # Renamed param
    # Important: Consider what happens to users whose active_node_id points to this node.
    # The API layer or a service layer should handle deactivating users from this node
    # or reassigning them *before* calling this low-level CRUD remove_node.
    # This function will just delete the node.
    # db.query(DBUser).filter(DBUser.active_node_id == dbnode_obj.id).update({"active_node_id": None}, synchronize_session=False)
    db.delete(dbnode_obj)
    db.commit()
    return dbnode_obj

def update_node(db: Session, dbnode_obj: Node, modify_data: NodeModify) -> Node: # Renamed params
    update_data = modify_data.model_dump(exclude_unset=True)
    original_status = dbnode_obj.status

    # Handle mTLS fields if they are present in the update data
    if 'panel_client_cert' in update_data:
        update_data['panel_client_cert_pem'] = update_data.pop('panel_client_cert')
    if 'panel_client_key' in update_data:
        update_data['panel_client_key_pem'] = update_data.pop('panel_client_key')

    for key, value in update_data.items():
        if hasattr(dbnode_obj, key): setattr(dbnode_obj, key, value)

    if 'status' in update_data:
        if dbnode_obj.status == NodeStatus.disabled:
            dbnode_obj.xray_version = None
            dbnode_obj.message = None
        elif original_status == NodeStatus.disabled and dbnode_obj.status != NodeStatus.disabled:
            dbnode_obj.status = NodeStatus.connecting

        if dbnode_obj.status != original_status:
            dbnode_obj.last_status_change = datetime.utcnow()

    db.commit()
    db.refresh(dbnode_obj)
    return dbnode_obj

def update_node_status(db: Session, dbnode_obj: Node, status: NodeStatus, message: Optional[str] = None, version: Optional[str] = None) -> Node: # Renamed param
    if dbnode_obj.status != status or dbnode_obj.message != message or (version is not None and dbnode_obj.xray_version != version):
        dbnode_obj.status = status
        dbnode_obj.message = message
        if version is not None: dbnode_obj.xray_version = version
        dbnode_obj.last_status_change = datetime.utcnow()
        db.commit()
        db.refresh(dbnode_obj)
    return dbnode_obj

# --- Notification Reminders --- (Largely unchanged)
def create_notification_reminder(db: Session, reminder_type: ReminderType, expires_at: datetime, user_id: int, threshold: Optional[int] = None) -> NotificationReminder:
    reminder = NotificationReminder(type=reminder_type, expires_at=expires_at, user_id=user_id, threshold=threshold)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder

def get_notification_reminder(db: Session, user_id: int, reminder_type: ReminderType, threshold: Optional[int] = None) -> Optional[NotificationReminder]:
    query = db.query(NotificationReminder).filter(
        NotificationReminder.user_id == user_id,
        NotificationReminder.type == reminder_type
    )
    if threshold is not None: query = query.filter(NotificationReminder.threshold == threshold)
    else: query = query.filter(NotificationReminder.threshold.is_(None)) # Match NULL thresholds if arg is None

    reminder = query.first()
    if reminder and reminder.expires_at and reminder.expires_at < datetime.utcnow():
        db.delete(reminder)
        db.commit()
        return None
    return reminder

def delete_notification_reminder_by_type(db: Session, user_id: int, reminder_type: ReminderType, threshold: Optional[int] = None):
    stmt = delete(NotificationReminder).where(
        NotificationReminder.user_id == user_id,
        NotificationReminder.type == reminder_type
    )
    if threshold is not None: stmt = stmt.where(NotificationReminder.threshold == threshold)
    else: stmt = stmt.where(NotificationReminder.threshold.is_(None))
    db.execute(stmt)
    db.commit()

def delete_notification_reminder(db: Session, dbreminder_obj: NotificationReminder): # Renamed param
    db.delete(dbreminder_obj)
    db.commit()

# --- Misc ---
def count_online_users(db: Session, hours: int = 24) -> int:
    time_threshold = datetime.utcnow() - timedelta(hours=hours)
    count = db.query(func.count(DBUser.id)).filter(DBUser.online_at.isnot(None), DBUser.online_at >= time_threshold).scalar()
    return count if count is not None else 0


# --- New CRUD functions for active node model ---
def get_users_by_active_node(db: Session, node_id: int) -> List[DBUser]:
    """
    Retrieves all users who have the specified node_id as their active_node_id.
    Eager loads relations consistent with get_user_queryset.
    """
    return get_user_queryset(db).filter(DBUser.active_node_id == node_id).all()


def get_proxy_hosts_by_node_id(db: Session, node_id: int) -> List[DBProxyHost]:
    """
    Retrieves all ProxyHost records associated with a specific node_id.
    """
    return db.query(DBProxyHost).filter(DBProxyHost.node_id == node_id).all()

def update_user_instance(db: Session, db_user: DBUser) -> DBUser:
    """
    Generic update for a user instance that's already been modified in the session.
    Adds to session (idempotent if already there), commits, and refreshes.
    """
    db.add(db_user) # Ensures the object is in the session if it wasn't already attached or was modified
    db.commit()
    db.refresh(db_user)
    return db_user

def get_users_for_usage_mapping(db: Session) -> List[Tuple[int, str]]:
    """
    Retrieves a list of (user_id, account_number) for all users.
    Used for mapping Xray user stats (which use email format like id.username) back to user IDs.
    """
    return db.query(DBUser.id, DBUser.account_number).all()


def create_or_update_node_user_usage(
    db: Session,
    user_id: int,
    node_id: Optional[int], # Can be None if somehow traffic is not node-specific (unlikely for this table)
    used_traffic_increment: int,
    event_hour_utc: datetime # This should be the specific hour (e.g., UTC, minute=0, second=0)
):
    """
    Creates or updates a NodeUserUsage record for a given user, node, and hour.
    If a record exists for that hour, it increments the used_traffic.
    Otherwise, it creates a new record.
    """
    if used_traffic_increment == 0:
        return # No change to record

    # Ensure event_hour_utc is truncated to the hour
    usage_hour = event_hour_utc.replace(minute=0, second=0, microsecond=0)

    existing_usage = db.query(NodeUserUsage).filter(
        NodeUserUsage.user_id == user_id,
        NodeUserUsage.node_id == node_id,
        NodeUserUsage.created_at == usage_hour
    ).first()

    if existing_usage:
        existing_usage.used_traffic += used_traffic_increment
    else:
        new_usage = NodeUserUsage(
            user_id=user_id,
            node_id=node_id,
            used_traffic=used_traffic_increment,
            created_at=usage_hour
        )
        db.add(new_usage)

    # Commit will be handled by the calling job after all updates for that run are processed.
    # If you want this to be atomic per call (less efficient for batching):
    # try:
    #     db.commit()
    # except Exception:
    #     db.rollback()
    #     raise


def aggregate_node_user_usages_to_node_usage(db: Session, event_datetime_utc: datetime):
    """
    Aggregates traffic from NodeUserUsage for each node for a specific hour
    and updates the NodeUsage table.
    The 'uplink' and 'downlink' in NodeUsage will store the total aggregated traffic.
    Xray user stats don't typically distinguish uplink/downlink per user, so we'll
    put the total into 'downlink' for NodeUsage as a convention, or you can split it.
    """
    aggregation_hour = event_datetime_utc.replace(minute=0, second=0, microsecond=0)

    # Get all distinct node_ids that had usage in NodeUserUsage for that hour
    # or iterate through all known nodes from the Node table.
    # Let's iterate through nodes that had NodeUserUsage entries.

    stmt_sum_traffic = (
        select(
            NodeUserUsage.node_id,
            func.sum(NodeUserUsage.used_traffic).label("total_traffic_for_hour")
        )
        .filter(NodeUserUsage.created_at == aggregation_hour)
        .group_by(NodeUserUsage.node_id)
    )

    aggregated_traffics = db.execute(stmt_sum_traffic).all()

    for node_id, total_traffic in aggregated_traffics:
        if total_traffic == 0:
            continue

        # For NodeUsage, we need to decide how to represent total_traffic as uplink/downlink
        # Option: Put all in downlink, or split 50/50 if no other info.
        # Let's put it all in downlink for simplicity, matching typical "download" accounting.
        current_uplink_increment = 0
        current_downlink_increment = total_traffic

        existing_node_usage = db.query(NodeUsage).filter(
            NodeUsage.node_id == node_id,
            NodeUsage.created_at == aggregation_hour
        ).first()

        if existing_node_usage:
            existing_node_usage.uplink += current_uplink_increment # Or however you attribute
            existing_node_usage.downlink += current_downlink_increment
        else:
            new_node_usage = NodeUsage(
                node_id=node_id,
                created_at=aggregation_hour,
                uplink=current_uplink_increment,
                downlink=current_downlink_increment
            )
            db.add(new_node_usage)

def get_panel_tls_credentials(db: Session) -> Optional[TLS]:
    """Returns the panel's client TLS ORM model instance from the DB, or None if not found."""
    return db.query(TLS).first()

def store_panel_tls_credentials(db: Session, key: str, certificate: str) -> TLS:
    """Stores or updates the panel's client TLS key and certificate in the database."""
    tls_entry = db.query(TLS).first()
    if not tls_entry:
        tls_entry = TLS(key=key, certificate=certificate)
        db.add(tls_entry)
    else:
        tls_entry.key = key
        tls_entry.certificate = certificate
    db.commit()
    db.refresh(tls_entry)
    return tls_entry