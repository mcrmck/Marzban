from functools import lru_cache
from typing import TYPE_CHECKING, Optional, Dict, List
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
import logging

from app import xray
from app.db import GetDB, crud
from app.db import models as db_models
from app.models.node import NodeStatus
from app.models.user import UserResponse
from app.models.proxy import ProxyTypes
from app.utils.concurrency import threaded_function
from app.xray.node import XRayNode
from xray_api.types.account import Account
from xray_api import XRay as XRayAPI # For type hinting api parameters


logger = logging.getLogger("marzban")



@lru_cache(maxsize=None)
def get_tls():
    """Get TLS certificate and key for node connections."""
    logger.debug("Fetching TLS certificate and key for node connections")
    with GetDB() as db:
        tls_orm = crud.get_panel_tls_credentials(db)
        if not tls_orm or not tls_orm.key or not tls_orm.certificate:
            logger.error("Panel's client TLS key or certificate not found in database. Panel <-> Node mTLS will fail if required by node.")
            return {"key": None, "certificate": None}
        logger.debug("Successfully retrieved TLS certificate and key")
        return {
            "key": tls_orm.key,
            "certificate": tls_orm.certificate
        }


@threaded_function
def _add_user_to_inbound(api: "XRayAPI", inbound_tag: str, account: Account):
    try:
        logger.debug(f"Attempting to add user {account.email} to inbound {inbound_tag} via API: {api}")
        api.add_inbound_user(tag=inbound_tag, user=account, timeout=30)
        logger.info(f"Successfully added user {account.email} to inbound {inbound_tag}")
    except xray.exc.EmailExistsError:
        logger.warning(f"User {account.email} already exists in inbound {inbound_tag}. Skipping add.")
        pass
    except xray.exc.ConnectionError as e:
        logger.error(f"Connection error while adding user {account.email} to {inbound_tag}: {e}")
        pass
    except Exception as e:
        logger.error(f"Unexpected error adding user {account.email} to {inbound_tag}: {e}", exc_info=True)
        pass


@threaded_function
def _remove_user_from_inbound(api: "XRayAPI", inbound_tag: str, email: str):
    try:
        logger.debug(f"Attempting to remove user {email} from inbound {inbound_tag} via API: {api}")
        api.remove_inbound_user(tag=inbound_tag, email=email, timeout=30)
        logger.info(f"Successfully removed user {email} from inbound {inbound_tag}")
    except xray.exc.EmailNotFoundError:
        logger.warning(f"User {email} not found in inbound {inbound_tag}. Skipping remove.")
        pass
    except xray.exc.ConnectionError as e:
        logger.error(f"Connection error while removing user {email} from {inbound_tag}: {e}")
        pass
    except Exception as e:
        logger.error(f"Unexpected error removing user {email} from {inbound_tag}: {e}", exc_info=True)
        pass


@threaded_function
def _alter_inbound_user(api: "XRayAPI", inbound_tag: str, account: Account):
    # This is essentially remove then add.
    email_to_remove = account.email
    try:
        logger.debug(f"Alter user: Attempting to remove {email_to_remove} from inbound {inbound_tag} via API: {api}")
        api.remove_inbound_user(tag=inbound_tag, email=email_to_remove, timeout=30)
        logger.info(f"Alter user: Successfully removed {email_to_remove} from inbound {inbound_tag} (or was not present)")
    except xray.exc.EmailNotFoundError:
        logger.warning(f"Alter user: {email_to_remove} not found in inbound {inbound_tag} during remove phase.")
        pass # It's okay if it wasn't there, we're adding it next.
    except xray.exc.ConnectionError as e:
        logger.error(f"Alter user: Connection error removing {email_to_remove} from {inbound_tag}: {e}. Will still attempt add.")
        pass # Log and proceed to add
    except Exception as e:
        logger.error(f"Alter user: Unexpected error removing {email_to_remove} from {inbound_tag}: {e}. Will still attempt add.")
        pass


    try:
        logger.debug(f"Alter user: Attempting to add {account.email} to inbound {inbound_tag} via API: {api}")
        api.add_inbound_user(tag=inbound_tag, user=account, timeout=30)
        logger.info(f"Alter user: Successfully added/updated {account.email} to inbound {inbound_tag}")
    except xray.exc.EmailExistsError:
        # This might happen if the initial remove failed silently due to connection but user still existed,
        # or if another process added it. Should be rare if remove worked.
        logger.warning(f"Alter user: {account.email} already exists in inbound {inbound_tag} during add phase. (This might indicate an issue if remove was expected to succeed)")
        pass
    except xray.exc.ConnectionError as e:
        logger.error(f"Alter user: Connection error adding {account.email} to {inbound_tag}: {e}")
        pass
    except Exception as e:
        logger.error(f"Alter user: Unexpected error adding {account.email} to {inbound_tag}: {e}")
        pass


@threaded_function
def remove_user(account_number: str): # Called when user is fully deleted
    logger.info(f"Xray Ops: Handling XRay cleanup for deleted user {account_number}.")
    with GetDB() as db: # Need DB to find their last active node
        # We fetch the user before they are deleted by the calling crud.remove_user
        # This assumes this XRay operation is scheduled *before* the DB row is gone.
        # If UserResponse is passed, use that. If only account_number, need to query.
        # Let's assume we can get their last active_node_id if needed.
        # For simplicity, let's assume the caller (API router) provides the active_node_id if known.
        # OR: this op is primarily for XRay, DB state is handled by router.
        # This function now only cares about XRay cleanup if an active node was known.
        # The router should pass the active_node_id at time of deletion.
        # So, this function might become:
        pass # This will be replaced by deactivate_user_from_active_node called by the router.
             # Or, if it must be generic:
        # with GetDB() as db:
        #    # This is problematic if user is already deleted from DB when this task runs.
        #    # The router *must* pass the active_node_id if it wants this to work.
        #    pass

@threaded_function
def update_user(user_id: int):
    """
    Updates a user's configuration on their active node.
    Creates and manages its own database session.
    """
    logger.info(f"Updating user ID {user_id}")
    with GetDB() as db:
        db_user = crud.get_user_by_id(db, user_id)
        if not db_user:
            logger.error(f"User {user_id} not found in database")
            return None

        if not db_user.active_node_id:
            logger.info(f"User ID {user_id} has no active node. No update needed.")
            return UserResponse.model_validate(db_user, context={'db': db})

        node = crud.get_node_by_id(db, db_user.active_node_id)
        if not node:
            logger.error(f"Node ID {db_user.active_node_id} not found in database.")
            return UserResponse.model_validate(db_user, context={'db': db})

        if node.status != NodeStatus.connected:
            logger.warning(f"Node ID {db_user.active_node_id} is not connected. Attempting to connect first.")
            connect_node(db_user.active_node_id)
            return UserResponse.model_validate(db_user, context={'db': db})

        node_instance = xray.nodes.get(db_user.active_node_id)
        if not node_instance:
            logger.error(f"Node ID {db_user.active_node_id} not found in xray.nodes.")
            return UserResponse.model_validate(db_user, context={'db': db})

        try:
            users_on_node = crud.get_users_by_active_node_id(db, db_user.active_node_id)
            xray.config.node_api_port = node.api_port
            node_specific_xray_config_obj = xray.config.build_node_config(node, users_on_node)

            node_instance.restart(node_specific_xray_config_obj)
            logger.info(f"Successfully updated user ID {user_id} on node ID {db_user.active_node_id}")

            return UserResponse.model_validate(db_user, context={'db': db})

        except Exception as e:
            logger.error(f"Failed to update user ID {user_id} on node ID {db_user.active_node_id}: {e}", exc_info=True)
            _change_node_status(db_user.active_node_id, NodeStatus.error, message=str(e))
            return UserResponse.model_validate(db_user, context={'db': db})

def _activate_user_on_xray_node_only(account_number: str, node_id: int):
    """Activate a user on an Xray node without updating the database."""
    logger.info(f"Activating user {account_number} on Xray node {node_id}")
    with GetDB() as db:
        db_node_orm = crud.get_node_by_id(db, node_id)
        if not db_node_orm:
            logger.error(f"Node ID {node_id} not found in database")
            return

        if db_node_orm.status != NodeStatus.connected:
            logger.warning(f"Node ID {node_id} is not connected. Attempting to connect first.")
            connect_node(node_id)
            return

        target_xray_node_instance = xray.nodes.get(node_id)
        if not target_xray_node_instance:
            logger.error(f"XRay Node {node_id} not found in xray.nodes")
            return

        if target_xray_node_instance and target_xray_node_instance.connected:
            try:
                xray.config.node_api_port = db_node_orm.api_port
                users_on_node = crud.get_users_by_active_node_id(db, node_id)
                db_user = crud.get_user(db, account_number)
                if db_user and db_user not in users_on_node:
                    users_on_node.append(db_user)

                node_specific_xray_config_obj = xray.config.build_node_config(db_node_orm, users_on_node)
                target_xray_node_instance.restart(node_specific_xray_config_obj)
                logger.info(f"Successfully activated user {account_number} on node {node_id}")

            except Exception as e:
                logger.error(f"Failed to activate user {account_number} on node {node_id}: {e}", exc_info=True)
                _change_node_status(node_id, NodeStatus.error, message=str(e))
        else:
            logger.error(f"XRay Node {node_id} ({db_node_orm.name}) not found or API not available for user {account_number}")


@threaded_function
def activate_user_on_node(account_number: str, node_id: int):
    """Activate a user on a specific node."""
    logger.info(f"Activating user {account_number} on node {node_id}")
    with GetDB() as db:
        db_user = crud.get_user(db, account_number)
        if not db_user:
            logger.error(f"User {account_number} not found")
            return None

        # Update user's active node
        db_user.active_node_id = node_id
        db_user.last_status_change = datetime.utcnow()
        crud.update_user_instance(db, db_user)

        # Activate user on Xray node
        _activate_user_on_xray_node_only(account_number, node_id)

        # Return updated user with proper context
        return UserResponse.model_validate(db_user, context={'db': db})


def get_node_specific_inbounds_for_user_proxy_type(node_id: int, proxy_type: ProxyTypes, db: Session) -> List[str]:
    """
    Get the list of inbound tags for a specific proxy type on a given node.
    This is determined by the node's service configurations.
    """
    # Get all service configurations for the given node_id
    node_service_configs = crud.get_services_for_node(db, node_id)

    relevant_tags = set()
    for service_config in node_service_configs:
        # Compare the service's protocol type with the user's proxy type
        if (service_config.protocol_type.value.lower() == proxy_type.value.lower() and
            service_config.enabled and
            service_config.xray_inbound_tag):
            relevant_tags.add(service_config.xray_inbound_tag)

    return list(relevant_tags)

@threaded_function
def _deactivate_user_from_xray_node_only(account_number: str, node_id: int):
    """
    Deactivates a user from a specific XRay node without modifying the database.
    Only handles the XRay configuration changes.
    """
    logger.info(f"Deactivating user {account_number} from XRay node {node_id} (XRay ops only).")
    xray_node_instance = xray.nodes.get(node_id)
    if xray_node_instance and xray_node_instance.api and xray_node_instance.connected:
        # Get the node's service configurations to know which inbounds to remove from
        with GetDB() as db:
            node_service_configs = crud.get_services_for_node(db, node_id)
            inbound_tags = [config.xray_inbound_tag for config in node_service_configs
                          if config.enabled and config.xray_inbound_tag]

            for inbound_tag in inbound_tags:
                _remove_user_from_inbound(xray_node_instance.api, inbound_tag, account_number)
    else:
        logger.warning(f"XRay Node {node_id} not found or API not available during deactivation for user {account_number}. XRay remove skipped.")


@threaded_function
def deactivate_user_from_active_node(account_number: str):
    """Deactivate a user from their active node."""
    logger.info(f"Starting deactivate_user_from_active_node operation for user {account_number}")
    with GetDB() as db:
        db_user = crud.get_user_by_account_number(db, account_number)
        if not db_user or not db_user.active_node_id:
            logger.info(f"User {account_number} not found or no active node to deactivate.")
            if db_user:
                return UserResponse.model_validate(db_user, context={'db': db})
            return None

        logger.debug(f"Found user {account_number} with active node ID {db_user.active_node_id}")
        node_id_to_deactivate = db_user.active_node_id
        _deactivate_user_from_xray_node_only(account_number, node_id_to_deactivate)

        logger.debug(f"Updating user {account_number} active_node_id to None")
        db_user.active_node_id = None
        db_user.last_status_change = datetime.utcnow()
        crud.update_user_instance(db, db_user)
        logger.info(f"User {account_number} deactivated from node {node_id_to_deactivate} and DB updated.")

        # Return updated user with proper context
        return UserResponse.model_validate(db_user, context={'db': db})


# Add new CRUD function for getting users by active node ID
def get_users_by_active_node_id(db: Session, node_id: int) -> List[db_models.User]:
    """Get all users with the given active_node_id, with their proxies loaded."""
    return db.query(db_models.User).options(
        joinedload(db_models.User.proxies)
    ).filter(
        db_models.User.active_node_id == node_id
    ).all()

# Add to crud module
crud.get_users_by_active_node_id = get_users_by_active_node_id

def _change_node_status(node_id: int, status: NodeStatus, message: Optional[str] = None, version: Optional[str] = None):
    """Helper to update node status in DB."""
    logger.debug(f"Changing node {node_id} status to {status.value}")
    with GetDB() as db:
        try:
            dbnode = crud.get_node_by_id(db, node_id)
            if not dbnode:
                logger.warning(f"_change_node_status: Node ID {node_id} not found in DB.")
                return

            if dbnode.status == NodeStatus.disabled and status != NodeStatus.disabled:
                logger.info(f"Node ID {node_id} is currently disabled in DB. Status change to {status.value} requested.")

            # Only update if there's a change to avoid unnecessary DB writes
            if dbnode.status != status or dbnode.message != message or dbnode.xray_version != version:
                crud.update_node_status(db, dbnode, status, message, version)
                logger.debug(f"Node ID {node_id} status updated in DB to: {status.value}, version: {version}, msg: {message}")

        except SQLAlchemyError as e:
            logger.error(f"DB error in _change_node_status for node ID {node_id}: {e}")
            db.rollback()
        except Exception as e:
            logger.error(f"Unexpected error in _change_node_status for node ID {node_id}: {e}", exc_info=True)

# Global to prevent multiple concurrent connection attempts to the same node
_connecting_nodes: Dict[int, bool] = {}

def connect_node(node_id: int):
    """
    Connects to a node and starts its Xray core with a node-specific configuration.
    """
    global _connecting_nodes

    if _connecting_nodes.get(node_id):
        logger.info(f"Node ID {node_id} connection already in progress. Skipping.")
        return

    try:
        _connecting_nodes[node_id] = True
        _change_node_status(node_id, NodeStatus.connecting, message="Attempting to connect and start Xray...")

        # Get node instance
        node_instance = xray.nodes.get(node_id)
        if not node_instance:
            with GetDB() as db:
                dbnode_for_connect = crud.get_node_by_id(db, node_id)
                if not dbnode_for_connect:
                    logger.error(f"connect_node: Node ID {node_id} not found in database. Cannot connect.")
                    return
                if dbnode_for_connect.status == NodeStatus.disabled:
                    logger.info(f"Node ID {node_id} ({dbnode_for_connect.name}) is disabled in DB. Skipping connection attempt.")
                    return
                logger.debug(f"Creating new XRayNode instance for node {dbnode_for_connect.name}")
                # Create new XRayNode instance and add it to xray.nodes dictionary
                node_instance = XRayNode(
                    node_id=dbnode_for_connect.id,
                    name=dbnode_for_connect.name,
                    address=dbnode_for_connect.address,
                    port=dbnode_for_connect.port,
                    api_port=dbnode_for_connect.api_port,
                    ssl_key_content=dbnode_for_connect.panel_client_key_pem,
                    ssl_cert_content=dbnode_for_connect.panel_client_cert_pem,
                    usage_coefficient=dbnode_for_connect.usage_coefficient,
                    node_type_preference=getattr(dbnode_for_connect, 'node_type_preference', None)
                )
                xray.nodes[node_id] = node_instance

        # Build node-specific config
        with GetDB() as db:
            node_orm = crud.get_node_by_id(db, node_id)
            if not node_orm:
                logger.error(f"connect_node: Node ID {node_id} not found in database during config build.")
                return

            # Load service configurations and users
            users_on_this_node = crud.get_users_by_active_node_id(db, node_id)
            logger.debug(f"Found {len(users_on_this_node)} users on node {node_orm.name}")

            # Use the global config instance
            logger.debug(f"Building node-specific config for node {node_orm.name}")
            xray.config.node_api_port = node_orm.api_port
            node_specific_xray_config_obj = xray.config.build_node_config(node_orm, users_on_this_node)

        # Start the node with its specific config
        logger.debug(f"Starting node {node_orm.name} with its specific config")
        node_instance.start(node_specific_xray_config_obj)
        version = node_instance.get_version()
        _change_node_status(node_id, NodeStatus.connected, version=version, message="Successfully connected and Xray started.")
        logger.info(f"Successfully connected to node \"{node_orm.name}\". Xray version: {version}")

    except Exception as e:
        logger.error(f"Failed to connect/start node ID {node_id}: {e}", exc_info=True)
        _change_node_status(node_id, NodeStatus.error, message=str(e))
        try:
            if node_instance and hasattr(node_instance, 'disconnect'):
                logger.debug(f"Attempting to disconnect node {node_id} after connection failure")
                node_instance.disconnect()
        except Exception as disc_e:
            logger.error(f"Error trying to disconnect node {node_id} after connection failure: {disc_e}")
    finally:
        if node_id in _connecting_nodes:
            del _connecting_nodes[node_id]

__all__ = [
    "add_user",
    "remove_user",
    "update_user",
    "add_node",
    "remove_node",
    "connect_node",
    "restart_node",
]