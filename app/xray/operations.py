from functools import lru_cache
from typing import TYPE_CHECKING, Optional, Dict, List
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError

from app import logger, xray # xray.api, xray.nodes, xray.config, xray.exc
from app.db import GetDB, crud # crud is used for node status updates
from app.db import models as db_models
from app.models.node import NodeStatus
from app.models.user import UserResponse, UserStatus # Added UserStatus
from app.models.proxy import ProxyTypes # To iterate user.proxies if needed
from app.utils.concurrency import threaded_function
from app.xray.node import XRayNode # For type hinting if node objects are passed directly
# from xray_api import XRay as XRayAPI # Already available via xray.api and node.api
from xray_api.types.account import Account, XTLSFlows # Account models for Xray API
from app.xray.config import XRayConfig
import config

if TYPE_CHECKING:
    # from app.db import User as DBUser # No longer directly type hinting DBUser in public functions
    from app.db.models import Node as DBNode # For add_node
    from xray_api import XRay as XRayAPI # For type hinting api parameters
    from app.db.models import NodeServiceConfiguration


@lru_cache(maxsize=None)
def get_tls():
    # This function is fine, uses its own DB session.
    from app.db import GetDB, get_tls_certificate # Local import
    with GetDB() as db:
        tls = get_tls_certificate(db)
        if not tls or not tls.key or not tls.certificate:
            logger.error("TLS key or certificate not found in database. Node operations requiring TLS may fail.")
            return {"key": None, "certificate": None} # Return defaults or raise
        return {
            "key": tls.key,
            "certificate": tls.certificate
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
        logger.error(f"Unexpected error adding user {account.email} to {inbound_tag}: {e}")
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
        logger.error(f"Unexpected error removing user {email} from {inbound_tag}: {e}")
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
    """
    with GetDB() as db:
        user = crud.get_user_by_id(db, user_id)
        if not user:
            logger.error(f"update_user: User ID {user_id} not found in database.")
            return

        if not user.active_node_id:
            logger.info(f"User ID {user_id} has no active node. No update needed.")
            return

        node = crud.get_node_by_id(db, user.active_node_id)
        if not node:
            logger.error(f"update_user: Node ID {user.active_node_id} not found in database.")
            return

        if node.status != NodeStatus.connected:
            logger.warning(f"Node ID {user.active_node_id} is not connected. Attempting to connect first.")
            connect_node(user.active_node_id)
            return

        node_instance = xray.nodes.get(user.active_node_id)
        if not node_instance:
            logger.error(f"update_user: Node ID {user.active_node_id} not found in xray.nodes.")
            return

        try:
            # Build node-specific config with updated user
            node_config_builder = XRayConfig(
                base_template_path=config.XRAY_CONFIG_PATH,
                node_api_port=node.api_port
            )
            users_on_node = crud.get_users_by_active_node_id(db, user.active_node_id)
            node_specific_xray_config_obj = node_config_builder.build_node_config(node, users_on_node)

            # Restart node with updated config
            node_instance.restart(node_specific_xray_config_obj)
            logger.info(f"Successfully updated user ID {user_id} on node ID {user.active_node_id}")

        except Exception as e:
            logger.error(f"Failed to update user ID {user_id} on node ID {user.active_node_id}: {e}", exc_info=True)
            _change_node_status(user.active_node_id, NodeStatus.error, message=str(e))

@threaded_function
def activate_user_on_node(user_id: int, node_id: int):
    """
    Activates a user on a specific node by updating their active_node_id and restarting the node.
    """
    with GetDB() as db:
        user = crud.get_user_by_id(db, user_id)
        if not user:
            logger.error(f"activate_user_on_node: User ID {user_id} not found in database.")
            return

        node = crud.get_node_by_id(db, node_id)
        if not node:
            logger.error(f"activate_user_on_node: Node ID {node_id} not found in database.")
            return

        if node.status != NodeStatus.connected:
            logger.warning(f"Node ID {node_id} is not connected. Attempting to connect first.")
            connect_node(node_id)
            return

        # Update user's active node
        user.active_node_id = node_id
        db.commit()

        node_instance = xray.nodes.get(node_id)
        if not node_instance:
            logger.error(f"activate_user_on_node: Node ID {node_id} not found in xray.nodes.")
            return

        try:
            # Build node-specific config with activated user
            node_config_builder = XRayConfig(
                base_template_path=config.XRAY_CONFIG_PATH,
                node_api_port=node.api_port
            )
            users_on_node = crud.get_users_by_active_node_id(db, node_id)
            node_specific_xray_config_obj = node_config_builder.build_node_config(node, users_on_node)

            # Restart node with updated config
            node_instance.restart(node_specific_xray_config_obj)
            logger.info(f"Successfully activated user ID {user_id} on node ID {node_id}")

        except Exception as e:
            logger.error(f"Failed to activate user ID {user_id} on node ID {node_id}: {e}", exc_info=True)
            _change_node_status(node_id, NodeStatus.error, message=str(e))

@threaded_function
def deactivate_user(user_id: int):
    """
    Deactivates a user by removing them from their active node and restarting the node.
    """
    with GetDB() as db:
        user = crud.get_user_by_id(db, user_id)
        if not user:
            logger.error(f"deactivate_user: User ID {user_id} not found in database.")
            return

        if not user.active_node_id:
            logger.info(f"User ID {user_id} has no active node. No deactivation needed.")
            return

        node_id = user.active_node_id
        node = crud.get_node_by_id(db, node_id)
        if not node:
            logger.error(f"deactivate_user: Node ID {node_id} not found in database.")
            return

        # Remove user from active node
        user.active_node_id = None
        db.commit()

        if node.status != NodeStatus.connected:
            logger.info(f"Node ID {node_id} is not connected. User deactivated in database only.")
            return

        node_instance = xray.nodes.get(node_id)
        if not node_instance:
            logger.error(f"deactivate_user: Node ID {node_id} not found in xray.nodes.")
            return

        try:
            # Build node-specific config without the deactivated user
            node_config_builder = XRayConfig(
                base_template_path=config.XRAY_CONFIG_PATH,
                node_api_port=node.api_port
            )
            users_on_node = crud.get_users_by_active_node_id(db, node_id)
            node_specific_xray_config_obj = node_config_builder.build_node_config(node, users_on_node)

            # Restart node with updated config
            node_instance.restart(node_specific_xray_config_obj)
            logger.info(f"Successfully deactivated user ID {user_id} from node ID {node_id}")

        except Exception as e:
            logger.error(f"Failed to deactivate user ID {user_id} from node ID {node_id}: {e}", exc_info=True)
            _change_node_status(node_id, NodeStatus.error, message=str(e))

# --- Node Management ---
# These functions seem mostly fine regarding their interaction with Xray nodes.
# The key is that `connect_node` and `restart_node` use `xray.config.include_db_users()`
# which generates the full config with all *currently active* users.

def remove_node(node_id: int):
    """Disconnects and removes a node from internal tracking."""
    if node_id in xray.nodes:
        node_to_remove = xray.nodes[node_id]
        logger.info(f"Removing node ID {node_id} ({node_to_remove.address if node_to_remove else 'N/A'}). Disconnecting if possible.")
        try:
            if hasattr(node_to_remove, 'disconnect') and callable(node_to_remove.disconnect):
                node_to_remove.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting node ID {node_id}: {e}")
        finally:
            try:
                del xray.nodes[node_id]
                logger.info(f"Node ID {node_id} removed from tracking.")
            except KeyError:
                logger.warning(f"Node ID {node_id} was already removed from tracking during disconnect.")
                pass


def add_node(dbnode: "DBNode") -> XRayNode: # Return XRayNode instance
    """
    Removes any existing tracked node with the same ID, then creates and tracks a new XRayNode instance.
    Uses the node's own panel_client_key_pem and panel_client_cert_pem for mTLS authentication.
    """
    logger.info(f"Adding/Re-adding node: {dbnode.name} (ID: {dbnode.id}), Address: {dbnode.address}:{dbnode.port}")
    remove_node(dbnode.id) # Ensure clean state

    # Check for required mTLS credentials
    if not dbnode.panel_client_key_pem or not dbnode.panel_client_cert_pem:
        error_msg = f"Cannot add node {dbnode.name} (ID: {dbnode.id}): Missing panel_client_key_pem or panel_client_cert_pem in database."
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(f"Creating XRayNode for dbnode: id={dbnode.id}, name='{dbnode.name}', "
                f"address='{dbnode.address}', port={dbnode.port}, api_port={dbnode.api_port}, "
                f"has_client_key={bool(dbnode.panel_client_key_pem)}, "
                f"has_client_cert={bool(dbnode.panel_client_cert_pem)}")

    new_xray_node_instance = XRayNode(
        node_id=dbnode.id,
        name=dbnode.name,
        address=dbnode.address,
        port=dbnode.port,  # This is the Marzban Node's ReST/RPyC API port (e.g., 6001)
        api_port=dbnode.api_port, # This is the XRay gRPC API port (e.g., 62051)
        ssl_key_content=dbnode.panel_client_key_pem,
        ssl_cert_content=dbnode.panel_client_cert_pem,
        usage_coefficient=dbnode.usage_coefficient,
        node_type_preference=getattr(dbnode, 'node_type_preference', None)
    )
    xray.nodes[dbnode.id] = new_xray_node_instance
    logger.info(f"Node {dbnode.name} (ID: {dbnode.id}) added to xray.nodes.")
    return new_xray_node_instance


def _change_node_status(node_id: int, status: NodeStatus, message: Optional[str] = None, version: Optional[str] = None):
    """Helper to update node status in DB."""
    with GetDB() as db:
        try:
            dbnode = crud.get_node_by_id(db, node_id)
            if not dbnode:
                logger.warning(f"_change_node_status: Node ID {node_id} not found in DB.")
                return

            if dbnode.status == NodeStatus.disabled and status != NodeStatus.disabled:
                # If trying to change status of a disabled node (other than to disabled again),
                # it implies it should be re-enabled. The connect_node logic handles this.
                # Here, we just log. The actual re-enabling is typically triggered elsewhere.
                logger.info(f"Node ID {node_id} is currently disabled in DB. Status change to {status.value} requested.")
                # If a disabled node is being re-enabled, its status might first go to 'connecting'.
                # However, if it's just a status update (e.g. to error while it was connecting), proceed.
                # This function primarily records the state.

            # Only update if there's a change to avoid unnecessary DB writes
            if dbnode.status != status or dbnode.message != message or dbnode.xray_version != version:
                 crud.update_node_status(db, dbnode, status, message, version)
                 logger.debug(f"Node ID {node_id} status updated in DB to: {status.value}, version: {version}, msg: {message}")
            # else:
                # logger.debug(f"Node ID {node_id} status ({status.value}) already matches DB. No DB update for status.")

        except SQLAlchemyError as e:
            logger.error(f"DB error in _change_node_status for node ID {node_id}: {e}")
            db.rollback()
        except Exception as e:
            logger.error(f"Unexpected error in _change_node_status for node ID {node_id}: {e}")


# Global to prevent multiple concurrent connection attempts to the same node
_connecting_nodes: Dict[int, bool] = {}


@threaded_function
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
                    remove_node(node_id)
                    return
                node_instance = add_node(dbnode_for_connect)

        # Build node-specific config
        with GetDB() as db:
            node_orm = crud.get_node_by_id(db, node_id)
            if not node_orm:
                logger.error(f"connect_node: Node ID {node_id} not found in database during config build.")
                return

            # Load service configurations and users
            users_on_this_node = crud.get_users_by_active_node_id(db, node_id)

            # Create and build node-specific config
            node_config_builder = XRayConfig(
                base_template_path=config.XRAY_CONFIG_PATH,
                node_api_port=node_orm.api_port
            )
            node_specific_xray_config_obj = node_config_builder.build_node_config(node_orm, users_on_this_node)

        # Start the node with its specific config
        node_instance.start(node_specific_xray_config_obj)
        version = node_instance.get_version()
        _change_node_status(node_id, NodeStatus.connected, version=version, message="Successfully connected and Xray started.")
        logger.info(f"Successfully connected to node \"{node_orm.name}\". Xray version: {version}")

    except Exception as e:
        logger.error(f"Failed to connect/start node ID {node_id}: {e}", exc_info=True)
        _change_node_status(node_id, NodeStatus.error, message=str(e))
        try:
            if node_instance and hasattr(node_instance, 'disconnect'):
                node_instance.disconnect()
        except Exception as disc_e:
            logger.error(f"Error trying to disconnect node {node_id} after connection failure: {disc_e}")
    finally:
        if node_id in _connecting_nodes:
            del _connecting_nodes[node_id]


@threaded_function
def restart_node(node_id: int):
    """
    Restarts the Xray core on a specific node with a node-specific configuration.
    """
    with GetDB() as db:
        dbnode_for_restart = crud.get_node_by_id(db, node_id)
        if not dbnode_for_restart:
            logger.error(f"restart_node: Node ID {node_id} not found in database. Cannot restart.")
            return

        if dbnode_for_restart.status == NodeStatus.disabled:
            logger.info(f"Node ID {node_id} ({dbnode_for_restart.name}) is disabled. Skipping restart.")
            return

    node_instance = xray.nodes.get(node_id)
    if not node_instance:
        logger.warning(f"Node ID {node_id} not found in tracked xray.nodes. Attempting to connect first.")
        connect_node(node_id)
        return

    if not node_instance.connected or not node_instance.started:
        logger.warning(f"Node ID {node_id} is not connected/started. Attempting to connect instead of restart.")
        connect_node(node_id)
        return

    try:
        _change_node_status(node_id, NodeStatus.connecting, message="Restarting Xray core...")

        # Build node-specific config
        with GetDB() as db:
            node_orm = crud.get_node_by_id(db, node_id)
            users_on_this_node = crud.get_users_by_active_node_id(db, node_id)

            # Create and build node-specific config
            node_config_builder = XRayConfig(
                base_template_path=config.XRAY_CONFIG_PATH,
                node_api_port=node_orm.api_port
            )
            node_specific_xray_config_obj = node_config_builder.build_node_config(node_orm, users_on_this_node)

        # Restart the node with its specific config
        node_instance.restart(node_specific_xray_config_obj)
        version = node_instance.get_version()
        _change_node_status(node_id, NodeStatus.connected, version=version, message="Xray core restarted successfully.")
        logger.info(f"Xray core of node \"{dbnode_for_restart.name}\" restarted. Current version: {version}")

    except Exception as e:
        logger.error(f"Failed to restart Xray core on node ID {node_id}: {e}", exc_info=True)
        _change_node_status(node_id, NodeStatus.error, message=str(e))
        try:
            if node_instance and hasattr(node_instance, 'disconnect'):
                node_instance.disconnect()
        except Exception as disc_e:
            logger.error(f"Error trying to disconnect node {node_id} after restart failure: {disc_e}")


@threaded_function # Keep operations non-blocking
def activate_user_on_node(account_number: str, node_id: int): # Simplified: get user from DB inside
    with GetDB() as db:
        db_user = crud.get_user(db, account_number)
        if not db_user:
            logger.error(f"Activate: User {account_number} not found.")
            return

        user_payload = UserResponse.model_validate(db_user) # For proxy settings

        # 1. Deactivate from old node (if any and different)
        if db_user.active_node_id and db_user.active_node_id != node_id:
            logger.info(f"User {account_number} switching from node {db_user.active_node_id} to {node_id}. Deactivating from old node.")
            # Call an internal helper that doesn't commit DB changes for active_node_id yet
            _deactivate_user_from_xray_node_only(db_user.account_number, db_user.active_node_id)

        # 2. Add to new node's XRay
        logger.info(f"Activating user {account_number} on XRay node {node_id}.")
        target_xray_node_instance = xray.nodes.get(node_id)
        if not target_xray_node_instance or not target_xray_node_instance.connected:
            # Attempt to connect the node if not available; this might be complex
            # For now, assume node is managed (connected/restarted) independently
            # If still not connected, we might need to fetch DBNode and attempt connection
            db_node = crud.get_node_by_id(db, node_id)
            if db_node and (not target_xray_node_instance or not target_xray_node_instance.connected):
                logger.warning(f"Target node {node_id} for user {account_number} not connected. Attempting to connect.")
                # connect_node itself is threaded, ensure it completes or XRayNode object is available
                # This part needs careful thought on synchronization if connect_node is slow.
                # For simplicity, we might require nodes to be pre-connected by an admin or a startup job.
                # Let's assume for now that if xray.nodes.get(node_id) is valid and connected, we proceed.
                # If not, we log an error and potentially skip XRay add, but still set active_node_id in DB.
                # Fallback: If connect_node is called, it should eventually add users if this node is their active_node_id.
                pass # Placeholder for more robust node connection handling if needed here

        if target_xray_node_instance and target_xray_node_instance.api:
            for proxy_type_enum, user_proxy_settings in user_payload.proxies.items():
                if not user_proxy_settings: continue
                account = proxy_type_enum.account_model(
                    email=user_payload.account_number,
                    **user_proxy_settings.model_dump(exclude_none=True)
                )
                # Determine relevant inbounds for this proxy_type on THIS node
                # This is the tricky part: how do we know which of user_payload.inbounds
                # are actually running on target_xray_node_instance?
                # Option: iterate all inbounds the user has for that proxy type,
                # and _add_user_to_inbound will try. If the inbound isn't on the node, it fails gracefully.
                node_specific_inbound_tags_for_type = get_node_specific_inbounds_for_user_proxy_type(node_id, proxy_type_enum, db)

                for inbound_tag in node_specific_inbound_tags_for_type:
                    # Apply XTLS flow logic from original add_user if necessary
                    inbound_config_details = xray.config.inbounds_by_tag.get(inbound_tag, {}) # Global config
                    if hasattr(account, 'flow') and getattr(account, 'flow', None) is not None:
                         if (inbound_config_details.get('network', 'tcp') not in ('tcp', 'kcp', 'raw') or
                            (inbound_config_details.get('network', 'tcp') in ('tcp', 'kcp', 'raw') and
                             inbound_config_details.get('tls') not in ('tls', 'reality')) or
                            inbound_config_details.get('header_type') == 'http'):
                            account.flow = getattr(XTLSFlows, 'NONE', None) # Ensure XTLSFlows.NONE is accessible

                    _add_user_to_inbound(target_xray_node_instance.api, inbound_tag, account)
        else:
            logger.error(f"XRay Node {node_id} not found or API not available for user {account_number}. XRay add skipped.")

        # 3. Update DB
        if db_user.active_node_id != node_id: # Avoid unnecessary DB write if already active on this node
            db_user.active_node_id = node_id
            db_user.last_status_change = datetime.utcnow() # Or a more specific "last_activation_change"
        crud.update_user_instance(db, db_user) # Generic update to commit changes
        logger.info(f"User {account_number} DB record updated, active_node_id set to {node_id}.")


def get_node_specific_inbounds_for_user_proxy_type(node_id: int, proxy_type: ProxyTypes, db: Session) -> List[str]:
    # This function needs to identify which global inbound_tags (of the given proxy_type)
    # are actually hosted on the specific node_id.
    # This could be achieved if ProxyHost is linked to Node and InboundTag.
    # Or if Node model stores info about which inbound_tags it serves.

    # Simplistic approach for now: get all ProxyHosts for the given node_id
    # Then, from those ProxyHosts, get their unique inbound_tags that match the proxy_type.
    node_proxy_hosts = crud.get_proxy_hosts_by_node_id(db, node_id) # New CRUD needed

    relevant_tags = set()
    for ph in node_proxy_hosts:
        inbound_detail = xray.config.inbounds_by_tag.get(ph.inbound_tag) # Global config
        if inbound_detail and inbound_detail.get("protocol") == proxy_type.value:
            relevant_tags.add(ph.inbound_tag)
    return list(relevant_tags)

@threaded_function
def _deactivate_user_from_xray_node_only(account_number: str, node_id: int):
    logger.info(f"Deactivating user {account_number} from XRay node {node_id} (XRay ops only).")
    xray_node_instance = xray.nodes.get(node_id)
    if xray_node_instance and xray_node_instance.api and xray_node_instance.connected:
        # Which inbounds to remove from? Ideally, only those the user was on.
        # Simplest: try removing from all known system inbounds on that node.
        # A better way: query the node's XRay API for this user's presence if possible, or rely on stored state.
        # For now, iterate global tags (as in original remove_user) but target specific node.
        all_system_inbound_tags = list(xray.config.inbounds_by_tag.keys()) # Or node-specific if known
        for inbound_tag in all_system_inbound_tags:
             _remove_user_from_inbound(xray_node_instance.api, inbound_tag, account_number)
    else:
        logger.warning(f"XRay Node {node_id} not found or API not available during deactivation for user {account_number}. XRay remove skipped.")


@threaded_function
def deactivate_user_from_active_node(account_number: str): # Gets user and active_node_id from DB
    with GetDB() as db:
        db_user = crud.get_user_by_account_number(db, account_number)
        if not db_user or not db_user.active_node_id:
            logger.info(f"User {account_number} not found or no active node to deactivate.")
            return

        node_id_to_deactivate = db_user.active_node_id
        _deactivate_user_from_xray_node_only(account_number, node_id_to_deactivate)

        db_user.active_node_id = None
        db_user.last_status_change = datetime.utcnow()
        crud.update_user_instance(db, db_user)
        logger.info(f"User {account_number} deactivated from node {node_id_to_deactivate} and DB updated.")


@lru_cache(maxsize=None)
def get_tls():
    # This function is fine, uses its own DB session.
    # from app.db import GetDB, get_tls_certificate # Original import
    with GetDB() as db:
        # Use the new CRUD function that returns the ORM model or key/cert directly
        tls_orm = crud.get_panel_tls_credentials(db) # MODIFIED LINE
        if not tls_orm or not tls_orm.key or not tls_orm.certificate:
            logger.error("Panel's client TLS key or certificate not found in database. Panel <-> Node mTLS will fail if required by node.")
            return {"key": None, "certificate": None}
        return {
            "key": tls_orm.key,
            "certificate": tls_orm.certificate
        }

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

__all__ = [
    "add_user",
    "remove_user",
    "update_user", # Added update_user to __all__
    "add_node",
    "remove_node",
    "connect_node",
    "restart_node",
]