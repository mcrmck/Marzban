from functools import lru_cache
from typing import TYPE_CHECKING, Optional, Dict

from sqlalchemy.exc import SQLAlchemyError

from app import logger, xray # xray.api, xray.nodes, xray.config, xray.exc
from app.db import GetDB, crud # crud is used for node status updates
from app.models.node import NodeStatus
from app.models.user import UserResponse # Expecting Pydantic UserResponse
from app.models.proxy import ProxyTypes # To iterate user.proxies if needed
from app.utils.concurrency import threaded_function
from app.xray.node import XRayNode # For type hinting if node objects are passed directly
# from xray_api import XRay as XRayAPI # Already available via xray.api and node.api
from xray_api.types.account import Account, XTLSFlows # Account models for Xray API

if TYPE_CHECKING:
    # from app.db import User as DBUser # No longer directly type hinting DBUser in public functions
    from app.db.models import Node as DBNode # For add_node
    from xray_api import XRay as XRayAPI # For type hinting api parameters


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


def add_user(user_payload: UserResponse):
    """
    Adds a user to all relevant Xray inbounds on the main core and connected nodes.
    Expects a Pydantic UserResponse model, which should have relationships (proxies, inbounds) resolved.
    """
    logger.info(f"Xray Ops: Adding user {user_payload.account_number}")
    email = user_payload.account_number # User's unique identifier for Xray

    # user_payload.inbounds is Dict[ProxyTypes, List[str (tag)]]
    # user_payload.proxies is Dict[ProxyTypes, ProxySettings (Pydantic)]
    for proxy_type_enum, inbound_tags_for_type in user_payload.inbounds.items():
        proxy_settings_pydantic = user_payload.proxies.get(proxy_type_enum)
        if not proxy_settings_pydantic:
            logger.warning(f"No proxy settings found for proxy type {proxy_type_enum.value} for user {email}, though inbounds are listed. Skipping Xray add for this type.")
            continue

        # Convert Pydantic ProxySettings to dict for the account model
        # Assuming .model_dump() is the Pydantic v2 way, or .dict() for v1
        try:
            proxy_settings_dict = proxy_settings_pydantic.model_dump(exclude_none=True)
        except AttributeError: # Fallback for Pydantic v1
            proxy_settings_dict = proxy_settings_pydantic.dict(exclude_none=True)


        # Create the Xray Account object
        # The account_model should be a method or attribute on ProxyTypes enum members
        try:
            if not hasattr(proxy_type_enum, 'account_model') or not callable(proxy_type_enum.account_model):
                logger.error(f"ProxyType {proxy_type_enum.value} does not have a callable 'account_model'. Cannot create Xray account.")
                continue
            account = proxy_type_enum.account_model(email=email, **proxy_settings_dict)
        except Exception as e:
            logger.error(f"Error creating Xray account model for user {email}, type {proxy_type_enum.value}: {e}")
            continue

        for inbound_tag in inbound_tags_for_type:
            inbound_config_details = xray.config.inbounds_by_tag.get(inbound_tag, {})
            if not inbound_config_details:
                logger.warning(f"Inbound tag {inbound_tag} not found in xray.config. Skipping for user {email}.")
                continue

            # Apply XTLS flow logic
            if hasattr(account, 'flow') and getattr(account, 'flow', None) is not None: # Check if flow attribute exists and is set
                if (inbound_config_details.get('network', 'tcp') not in ('tcp', 'kcp', 'raw') or # Added 'raw'
                    (inbound_config_details.get('network', 'tcp') in ('tcp', 'kcp', 'raw') and
                     inbound_config_details.get('tls') not in ('tls', 'reality')) or
                    inbound_config_details.get('header_type') == 'http'):
                    account.flow = XTLSFlows.NONE # Assuming XTLSFlows.NONE is defined

            if xray.api:
                _add_user_to_inbound(xray.api, inbound_tag, account)
            else:
                logger.warning("Main Xray API (xray.api) is not initialized. Cannot add user to core.")

            for node_instance in list(xray.nodes.values()): # Iterate over XRayNode instances
                if node_instance.connected and node_instance.started and node_instance.api:
                    _add_user_to_inbound(node_instance.api, inbound_tag, account)
                # else:
                    # logger.debug(f"Node {node_instance.address} not connected/started or API not available. Skipping add user {email} to inbound {inbound_tag}.")


def remove_user(account_number: str):
    """
    Removes a user from all Xray inbounds on the main core and connected nodes.
    Expects the user's account_number (used as email in Xray).
    """
    logger.info(f"Xray Ops: Removing user {account_number}")
    email = account_number

    # Iterate through all known inbound tags in the system configuration
    for inbound_tag in xray.config.inbounds_by_tag.keys():
        if xray.api:
            _remove_user_from_inbound(xray.api, inbound_tag, email)
        # else: # Log if main API not available, but still try nodes
            # logger.warning("Main Xray API (xray.api) is not initialized. Cannot remove user from core.")

        for node_instance in list(xray.nodes.values()):
            if node_instance.connected and node_instance.started and node_instance.api:
                _remove_user_from_inbound(node_instance.api, inbound_tag, email)
            # else:
                # logger.debug(f"Node {node_instance.address} not connected/started or API not available. Skipping remove user {email} from inbound {inbound_tag}.")


def update_user(user_payload: UserResponse):
    """
    Updates a user on all relevant Xray inbounds (adds to new, removes from old, alters existing).
    Expects a Pydantic UserResponse model.
    """
    logger.info(f"Xray Ops: Updating user {user_payload.account_number}")
    email = user_payload.account_number

    current_active_inbound_tags_for_user = set()
    for proxy_type_enum, inbound_tags_for_type in user_payload.inbounds.items():
        proxy_settings_pydantic = user_payload.proxies.get(proxy_type_enum)
        if not proxy_settings_pydantic:
            logger.warning(f"Update: No proxy settings for type {proxy_type_enum.value} for user {email}. Skipping Xray update for this type.")
            continue

        try:
            proxy_settings_dict = proxy_settings_pydantic.model_dump(exclude_none=True)
        except AttributeError:
            proxy_settings_dict = proxy_settings_pydantic.dict(exclude_none=True)

        try:
            if not hasattr(proxy_type_enum, 'account_model') or not callable(proxy_type_enum.account_model):
                logger.error(f"Update: ProxyType {proxy_type_enum.value} no 'account_model'. Cannot create Xray account.")
                continue
            account = proxy_type_enum.account_model(email=email, **proxy_settings_dict)
        except Exception as e:
            logger.error(f"Update: Error creating Xray account model for user {email}, type {proxy_type_enum.value}: {e}")
            continue

        for inbound_tag in inbound_tags_for_type:
            current_active_inbound_tags_for_user.add(inbound_tag)
            inbound_config_details = xray.config.inbounds_by_tag.get(inbound_tag, {})
            if not inbound_config_details:
                logger.warning(f"Update: Inbound tag {inbound_tag} not in xray.config. Skipping for user {email}.")
                continue

            if hasattr(account, 'flow') and getattr(account, 'flow', None) is not None:
                if (inbound_config_details.get('network', 'tcp') not in ('tcp', 'kcp', 'raw') or
                    (inbound_config_details.get('network', 'tcp') in ('tcp', 'kcp', 'raw') and
                     inbound_config_details.get('tls') not in ('tls', 'reality')) or
                    inbound_config_details.get('header_type') == 'http'):
                    account.flow = XTLSFlows.NONE

            if xray.api:
                _alter_inbound_user(xray.api, inbound_tag, account)
            # else:
                # logger.warning("Update: Main Xray API not initialized. Cannot alter user on core.")

            for node_instance in list(xray.nodes.values()):
                if node_instance.connected and node_instance.started and node_instance.api:
                    _alter_inbound_user(node_instance.api, inbound_tag, account)
                # else:
                    # logger.debug(f"Update: Node {node_instance.address} not ready. Skipping alter user {email} on inbound {inbound_tag}.")

    # Remove user from any inbounds they are no longer supposed to be on
    all_system_inbound_tags = set(xray.config.inbounds_by_tag.keys())
    inbounds_to_remove_user_from = all_system_inbound_tags - current_active_inbound_tags_for_user

    for inbound_tag_to_remove in inbounds_to_remove_user_from:
        logger.debug(f"Update: User {email} no longer active on inbound {inbound_tag_to_remove}. Removing.")
        if xray.api:
            _remove_user_from_inbound(xray.api, inbound_tag_to_remove, email)
        # else:
            # logger.warning(f"Update: Main Xray API not initialized. Cannot remove user from {inbound_tag_to_remove} on core.")

        for node_instance in list(xray.nodes.values()):
            if node_instance.connected and node_instance.started and node_instance.api:
                _remove_user_from_inbound(node_instance.api, inbound_tag_to_remove, email)
            # else:
                # logger.debug(f"Update: Node {node_instance.address} not ready. Skipping remove user {email} from {inbound_tag_to_remove}.")


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
    """
    logger.info(f"Adding/Re-adding node: {dbnode.name} (ID: {dbnode.id}), Address: {dbnode.address}:{dbnode.api_port}")
    remove_node(dbnode.id) # Ensure clean state

    tls_config = get_tls()
    if not tls_config.get("key") or not tls_config.get("certificate"):
        logger.error(f"Cannot add node {dbnode.name} (ID: {dbnode.id}): TLS key/certificate is missing from DB.")
        # Depending on how critical TLS is for node communication, you might raise an error
        # or allow adding the node in a non-operational state.
        # For now, it will proceed but XRayNode might fail to connect if SSL is mandatory.

    new_xray_node_instance = XRayNode(address=dbnode.address,
                                     port=dbnode.port, # This is likely the proxy port, not API port for XRayNode connection
                                     api_port=dbnode.api_port, # This is the Xray API port for XRayNode
                                     ssl_key=tls_config['key'],
                                     ssl_cert=tls_config['certificate'],
                                     usage_coefficient=dbnode.usage_coefficient)
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
def connect_node(node_id: int, config=None):
    """
    Connects to a node, starts its Xray core with the given config (or full user config).
    """
    global _connecting_nodes

    if _connecting_nodes.get(node_id):
        logger.info(f"Node ID {node_id} connection already in progress. Skipping.")
        return

    dbnode_for_connect: Optional["DBNode"] = None # Ensure type hint
    with GetDB() as db: # Fetch DBNode details within this session
        dbnode_for_connect = crud.get_node_by_id(db, node_id)

    if not dbnode_for_connect:
        logger.error(f"connect_node: Node ID {node_id} not found in database. Cannot connect.")
        return

    if dbnode_for_connect.status == NodeStatus.disabled:
        logger.info(f"Node ID {node_id} ({dbnode_for_connect.name}) is disabled in DB. Skipping connection attempt.")
        remove_node(node_id) # Ensure it's not in the active xray.nodes tracking
        return

    node_instance: Optional[XRayNode] = xray.nodes.get(dbnode_for_connect.id)
    if not node_instance or (hasattr(node_instance, 'connected') and not node_instance.connected):
        # If not tracked or explicitly not connected, (re)add it.
        # add_node internally calls remove_node, so it ensures a fresh XRayNode object.
        logger.info(f"Node ID {node_id} not found in xray.nodes or not connected. Attempting to (re)add.")
        node_instance = add_node(dbnode_for_connect) # add_node returns the XRayNode instance
        if not node_instance: # Should not happen if add_node is robust
            logger.error(f"Failed to obtain XRayNode instance for node ID {node_id} in connect_node.")
            return

    # At this point, node_instance should be a valid XRayNode object from xray.nodes

    try:
        _connecting_nodes[node_id] = True
        _change_node_status(node_id, NodeStatus.connecting, message="Attempting to connect and start Xray...")
        logger.info(f"Connecting to node \"{dbnode_for_connect.name}\" (ID: {node_id})")

        if config is None:
            logger.debug(f"No specific config provided for node {node_id}, generating full user config.")
            config = xray.config.include_db_users() # This generates the XRayConfig object

        node_instance.start(config) # Pass the XRayConfig object (which is a dict subclass)
        version = node_instance.get_version()
        _change_node_status(node_id, NodeStatus.connected, version=version, message="Successfully connected and Xray started.")
        logger.info(f"Successfully connected to node \"{dbnode_for_connect.name}\". Xray version: {version}")

    except Exception as e:
        logger.error(f"Failed to connect/start node \"{dbnode_for_connect.name}\" (ID: {node_id}): {e}", exc_info=True)
        _change_node_status(node_id, NodeStatus.error, message=str(e))
        # Optionally try to disconnect if start failed partially
        try:
            if node_instance and hasattr(node_instance, 'disconnect'):
                node_instance.disconnect()
        except Exception as disc_e:
            logger.error(f"Error trying to disconnect node {node_id} after connection failure: {disc_e}")
    finally:
        if node_id in _connecting_nodes:
            del _connecting_nodes[node_id]


@threaded_function
def restart_node(node_id: int, config=None):
    """
    Restarts the Xray core on a specific node with the given config (or full user config).
    """
    dbnode_for_restart: Optional["DBNode"] = None
    with GetDB() as db:
        dbnode_for_restart = crud.get_node_by_id(db, node_id)

    if not dbnode_for_restart:
        logger.error(f"restart_node: Node ID {node_id} not found in database. Cannot restart.")
        return

    if dbnode_for_restart.status == NodeStatus.disabled:
        logger.info(f"Node ID {node_id} ({dbnode_for_restart.name}) is disabled. Skipping restart.")
        return

    node_instance = xray.nodes.get(dbnode_for_restart.id)
    if not node_instance:
        logger.warning(f"Node ID {node_id} not found in tracked xray.nodes. Attempting to add and connect first.")
        # If node isn't tracked, it implies it wasn't connected. Try to connect it.
        connect_node(node_id, config) # connect_node will handle adding it to xray.nodes
        return # connect_node is threaded, so this function call ends here.

    if not node_instance.connected or not node_instance.started:
        logger.warning(f"Node ID {node_id} ({dbnode_for_restart.name}) is not connected/started. Attempting to connect instead of restart.")
        connect_node(node_id, config)
        return

    try:
        _change_node_status(node_id, NodeStatus.connecting, message="Restarting Xray core...") # Show as connecting during restart
        logger.info(f"Restarting Xray core of node \"{dbnode_for_restart.name}\" (ID: {node_id})")

        if config is None:
            logger.debug(f"No specific config provided for node {node_id} restart, generating full user config.")
            config = xray.config.include_db_users()

        node_instance.restart(config) # Pass XRayConfig object
        version = node_instance.get_version() # Get version after restart
        _change_node_status(node_id, NodeStatus.connected, version=version, message="Xray core restarted successfully.")
        logger.info(f"Xray core of node \"{dbnode_for_restart.name}\" restarted. Current version: {version}")

    except Exception as e:
        logger.error(f"Failed to restart Xray core on node \"{dbnode_for_restart.name}\" (ID: {node_id}): {e}", exc_info=True)
        _change_node_status(node_id, NodeStatus.error, message=str(e))
        try:
            if node_instance and hasattr(node_instance, 'disconnect'):
                node_instance.disconnect()
        except Exception as disc_e:
            logger.error(f"Error trying to disconnect node {node_id} after restart failure: {disc_e}")


__all__ = [
    "add_user",
    "remove_user",
    "update_user", # Added update_user to __all__
    "add_node",
    "remove_node",
    "connect_node",
    "restart_node",
]