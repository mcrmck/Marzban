import asyncio
import time
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, WebSocket
from sqlalchemy.exc import IntegrityError
from starlette.websockets import WebSocketDisconnect

from app import logger, xray
from app.db import Session, crud, get_db, GetDB
from app.dependencies import get_dbnode, validate_dates
from app.models.admin import Admin
from app.models.node import (
    NodeCreate,
    NodeModify,
    NodeResponse,
    NodeSettings,
    NodeStatus,
    NodesUsageResponse,
)
from app.models.proxy import ProxyHostModify, ProxyHostSecurity
from app.models.node import Node as DBNode

from app.utils import responses

# Constants
LOG_BATCH_INTERVAL = 0.5  # Seconds between log batch sends

router = APIRouter(
    tags=["Node"], prefix="/api", responses={401: responses._401, 403: responses._403}
)


def add_host_if_needed(dbnode_id: int, create_hosts_flag: bool): # Takes node_id
    """Add a host for every inbound if specified flag is true, linked to the node."""
    if not create_hosts_flag:
        logger.info(f"Node ID {dbnode_id}: add_as_new_host is false. Skipping ProxyHost creation.")
        return

    with GetDB() as db: # Background task creates its own DB session
        dbnode = crud.get_node_by_id(db, dbnode_id)
        if not dbnode:
            logger.error(f"add_host_if_needed: Node ID {dbnode_id} not found. Cannot create hosts.")
            return

        logger.info(f"Node '{dbnode.name}' (ID: {dbnode.id}): add_as_new_host is true. Creating ProxyHost entries.")

        # Ensure xray.config is accessible; it holds the template inbounds
        if not hasattr(xray, 'config') or not hasattr(xray.config, 'inbounds_by_tag'):
            logger.error("xray.config or xray.config.inbounds_by_tag not available in add_host_if_needed. Cannot create hosts.")
            return

        created_hosts_count = 0
        for inbound_tag, inbound_details in xray.config.inbounds_by_tag.items():
            protocol = inbound_details.get("protocol", "PROTOCOL").upper()
            # transport = inbound_details.get("streamSettings", {}).get("network", "TRANSPORT").upper() # Original, but might be confusing
            transport = inbound_details.get("network", "TRANSPORT").upper() # Get network directly from resolved inbound

            host_remark = f"{dbnode.name} ({inbound_tag}) [{protocol} - {transport}]"
            host_address = dbnode.address # Use the node's address
            host_port = inbound_details.get("port") # Port from the resolved inbound details

            # For SNI/Host, using node's address is a sensible default.
            # Security and path can also be derived from resolved inbound_details.
            default_sni = dbnode.address
            default_host_header = dbnode.address
            default_path = inbound_details.get("path", "")

            # Determine security. If inbound_details has 'tls' (e.g., 'tls', 'reality'), map to ProxyHostSecurity enum.
            inbound_tls_setting = inbound_details.get("tls") # This is 'tls', 'reality', or 'none' from resolved config
            host_security_enum = ProxyHostSecurity.inbound_default # Default
            if inbound_tls_setting == "tls":
                host_security_enum = ProxyHostSecurity.tls
            elif inbound_tls_setting == "reality":
                host_security_enum = ProxyHostSecurity.reality
            elif inbound_tls_setting == "none": # explicit none
                host_security_enum = ProxyHostSecurity.none


            host_data = ProxyHostModify(
                remark=host_remark,
                address=host_address,
                node_id=dbnode.id, # Crucially, link this host to the new node
                port=host_port,
                sni=default_sni, # Default based on node address
                host=default_host_header, # Default based on node address
                security=host_security_enum,
                path=default_path, # Default based on resolved inbound path
                is_disabled=False,
                # Set other ProxyHostModify fields to sensible defaults if needed
                # alpn, fingerprint, allowinsecure, mux_enable etc. will take their defaults from Pydantic model
            )
            try:
                # crud.add_host in your provided crud.py takes (db, inbound_tag, host_data, node_id)
                # but ProxyHostModify now includes node_id.
                # Let's assume crud.add_host is adapted or we call a more direct creation.
                # For now, assuming it can take host_data which includes node_id.
                # If crud.add_host expects node_id separately, adjust this call.
                # Based on your crud.py, add_host takes:
                # add_host(db: Session, inbound_tag: str, host_data: ProxyHostModify, node_id: Optional[int] = None)
                # The node_id in host_data should be sufficient. The extra node_id param in add_host might be redundant.
                # Let's pass it anyway if the function expects it.
                crud.add_host(db, inbound_tag, host_data, node_id=dbnode.id)
                created_hosts_count += 1
            except Exception as e:
                logger.error(f"Failed to add host for inbound_tag '{inbound_tag}' on node '{dbnode.name}': {e}", exc_info=True)

        if created_hosts_count > 0 and hasattr(xray, 'hosts') and callable(getattr(xray.hosts, 'update', None)):
            logger.info(f"Created {created_hosts_count} new proxy hosts for node {dbnode.name}. Updating xray.hosts.")
            xray.hosts.update() # Presumed to reload host configurations
        elif created_hosts_count == 0:
            logger.info(f"No new proxy hosts created for node {dbnode.name} based on current xray.config inbounds.")


@router.get("/node/settings", response_model=NodeSettings)
def get_node_settings(
    db: Session = Depends(get_db)
):
    """Retrieve the current node settings, including TLS certificate. Public endpoint."""
    tls = crud.get_tls_certificate(db)
    return NodeSettings(certificate=tls.certificate)


@router.post("/node", response_model=NodeResponse, responses={409: responses._409})
def add_node(
    new_node: NodeCreate,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """Add a new node to the database and optionally add it as a host."""
    try:
        dbnode = crud.create_node(db, new_node)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f'Node "{new_node.name}" already exists'
        )

    bg.add_task(xray.operations.connect_node, node_id=dbnode.id)
    bg.add_task(add_host_if_needed, dbnode_id=dbnode.id, create_hosts_flag=new_node.add_as_new_host)

    logger.info(f'New node "{dbnode.name}" added')
    return dbnode


@router.get("/node/{node_id}", response_model=NodeResponse)
def get_node(
    dbnode: NodeResponse = Depends(get_dbnode),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """Retrieve details of a specific node by its ID."""
    return dbnode


@router.websocket("/node/{node_id}/logs")
async def node_logs(node_id: int, websocket: WebSocket, db: Session = Depends(get_db)):
    token = websocket.query_params.get("token") or websocket.headers.get(
        "Authorization", ""
    ).removeprefix("Bearer ")

    logger.info(f"Node logs WS: Attempting connection for node_id {node_id} with token prefix: {token[:20]}...") # Log token prefix

    admin = Admin.get_admin(token, db)
    if not admin:
        logger.warning(f"Node logs WS: Unauthorized for node_id {node_id}. Admin not found for token.")
        return await websocket.close(reason="Unauthorized", code=4401)

    # Log the admin details fetched
    logger.info(f"Node logs WS: Admin '{admin.username}' attempting access to logs for node_id {node_id}. Is Sudo: {admin.is_sudo}")

    if not admin.is_sudo:
        logger.warning(f"Node logs WS: Access denied for admin '{admin.username}' to node_id {node_id} logs. Reason: Not a sudo admin.")
        return await websocket.close(reason="You're not allowed", code=4403)

    if not xray.nodes.get(node_id):
        logger.warning(f"Node logs WS: Node ID {node_id} not found in tracked xray.nodes.")
        return await websocket.close(reason="Node not found", code=4404)

    node_instance = xray.nodes[node_id] # Get the node instance more safely
    if not node_instance.connected:
        logger.warning(f"Node logs WS: Node ID {node_id} ('{node_instance.address}') is not connected. Attempting to connect...")
        try:
            # Try to connect the node
            xray.operations.connect_node(node_id)
            # Wait for connection with timeout
            for _ in range(10):  # Try for 5 seconds (10 * 0.5)
                if node_instance.connected:
                    break
                await asyncio.sleep(0.5)

            if not node_instance.connected:
                logger.warning(f"Node logs WS: Node ID {node_id} failed to connect within timeout.")
                return await websocket.close(reason="Node connection timeout", code=4400)
        except Exception as e:
            logger.error(f"Node logs WS: Error connecting to node {node_id}: {e}")
            return await websocket.close(reason="Node connection error", code=4400)

    await websocket.accept()

    cache = ""
    last_sent_ts = 0
    node = xray.nodes[node_id]
    with node.get_logs() as logs:
        while True:
            if not node == xray.nodes[node_id]:
                break

            if LOG_BATCH_INTERVAL and time.time() - last_sent_ts >= LOG_BATCH_INTERVAL and cache:
                try:
                    await websocket.send_text(cache)
                except (WebSocketDisconnect, RuntimeError):
                    break
                cache = ""
                last_sent_ts = time.time()

            if not logs:
                try:
                    await asyncio.wait_for(websocket.receive(), timeout=0.2)
                    continue
                except asyncio.TimeoutError:
                    continue
                except (WebSocketDisconnect, RuntimeError):
                    break

            log = logs.popleft()

            if LOG_BATCH_INTERVAL:
                cache += f"{log}\n"
                continue

            try:
                await websocket.send_text(log)
            except (WebSocketDisconnect, RuntimeError):
                break


@router.get("/nodes", response_model=List[NodeResponse])
def get_nodes(
    db: Session = Depends(get_db)
):
    """Retrieve a list of all nodes. Public endpoint."""
    return crud.get_nodes(db)


@router.put("/node/{node_id}", response_model=NodeResponse)
def modify_node(
    modified_node: NodeModify,
    bg: BackgroundTasks,
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """Update a node's details. Only accessible to sudo admins."""
    updated_node = crud.update_node(db, dbnode, modified_node)
    xray.operations.remove_node(updated_node.id)
    if updated_node.status != NodeStatus.disabled:
        bg.add_task(xray.operations.connect_node, node_id=updated_node.id)

    logger.info(f'Node "{dbnode.name}" modified')
    return dbnode


@router.post("/node/{node_id}/reconnect")
def reconnect_node(
    bg: BackgroundTasks,
    dbnode: NodeResponse = Depends(get_node),
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """Trigger a reconnection for the specified node. Only accessible to sudo admins."""
    bg.add_task(xray.operations.connect_node, node_id=dbnode.id)
    return {"detail": "Reconnection task scheduled"}


@router.delete("/node/{node_id}")
def remove_node(
    dbnode: NodeResponse = Depends(get_node),
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin),
):
    """Delete a node and remove it from xray in the background."""
    crud.remove_node(db, dbnode)
    xray.operations.remove_node(dbnode.id)

    logger.info(f'Node "{dbnode.name}" deleted')
    return {}


@router.get("/nodes/usage", response_model=NodesUsageResponse)
def get_usage(
    db: Session = Depends(get_db),
    start: str = "",
    end: str = "",
    _: Admin = Depends(Admin.check_sudo_admin),
):
    """Retrieve usage statistics for nodes within a specified date range."""
    start, end = validate_dates(start, end)

    usages = crud.get_nodes_usage(db, start, end)

    return {"usages": usages}
