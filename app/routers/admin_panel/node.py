import asyncio
import time
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, WebSocket
from sqlalchemy.exc import IntegrityError
from starlette.websockets import WebSocketDisconnect

import logging
from app import xray
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
from app.models.node import Node as DBNode

from app.utils import responses

# Constants
LOG_BATCH_INTERVAL = 0.5  # Seconds between log batch sends

router = APIRouter(
    tags=["Node"], responses={401: responses._401, 403: responses._403}
)


@router.get("/node/settings", response_model=NodeSettings)
def get_node_settings(
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.get_current)
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
    """Add a new node to the database with automatic certificate generation."""
    try:
        # Create the node in database first
        dbnode = crud.create_node(db, new_node)
        
        # Automatically generate certificates for the new node
        from app.services.certificate_manager import CertificateManager
        cert_manager = CertificateManager(db)
        
        try:
            # Check if certificates already exist for this node
            node_certs = cert_manager.get_node_certificates(dbnode.name)
            
            if not node_certs:
                # Generate new certificates using node name and address
                node_certs = cert_manager.generate_node_certificates(
                    node_name=dbnode.name,
                    node_address=dbnode.address
                )
                logging.getLogger("marzban").info(
                    f'New certificates generated for node "{dbnode.name}"'
                )
            else:
                logging.getLogger("marzban").info(
                    f'Using existing certificates for node "{dbnode.name}"'
                )
            
            # Update the node with the generated client certificates
            # This stores the panel's client cert in the existing node table fields
            dbnode.panel_client_cert_pem = node_certs.panel_client_cert.certificate_pem
            dbnode.panel_client_key_pem = node_certs.panel_client_cert.private_key_pem
            db.commit()
            
            
        except Exception as cert_error:
            logging.getLogger("marzban").warning(
                f'Failed to generate certificates for node "{dbnode.name}": {cert_error}'
            )
            # Don't fail the node creation if certificate generation fails
            # The certificates can be generated later via the certificate management API
            
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f'Node "{new_node.name}" already exists'
        )

    bg.add_task(xray.operations.connect_node, node_id=dbnode.id)

    logging.getLogger("marzban").info(f'New node "{dbnode.name}" added with automatic certificate generation')
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

    logging.getLogger("marzban").info(f"Node logs WS: Attempting connection for node_id {node_id} with token prefix: {token[:20]}...") # Log token prefix

    admin = Admin.get_admin(token, db)
    if not admin:
        logging.getLogger("marzban").warning(f"Node logs WS: Unauthorized for node_id {node_id}. Admin not found for token.")
        return await websocket.close(reason="Unauthorized", code=4401)

    # Log the admin details fetched
    logging.getLogger("marzban").info(f"Node logs WS: Admin '{admin.username}' attempting access to logs for node_id {node_id}. Is Sudo: {admin.is_sudo}")

    if not admin.is_sudo:
        logging.getLogger("marzban").warning(f"Node logs WS: Access denied for admin '{admin.username}' to node_id {node_id} logs. Reason: Not a sudo admin.")
        return await websocket.close(reason="You're not allowed", code=4403)

    if not xray.nodes.get(node_id):
        logging.getLogger("marzban").warning(f"Node logs WS: Node ID {node_id} not found in tracked xray.nodes.")
        return await websocket.close(reason="Node not found", code=4404)

    node_instance = xray.nodes[node_id] # Get the node instance more safely
    if not node_instance.connected:
        logging.getLogger("marzban").warning(f"Node logs WS: Node ID {node_id} ('{node_instance.address}') is not connected. Attempting to connect...")
        try:
            # Try to connect the node
            xray.operations.connect_node(node_id)
            # Wait for connection with timeout
            for _ in range(10):  # Try for 5 seconds (10 * 0.5)
                if node_instance.connected:
                    break
                await asyncio.sleep(0.5)

            if not node_instance.connected:
                logging.getLogger("marzban").warning(f"Node logs WS: Node ID {node_id} failed to connect within timeout.")
                return await websocket.close(reason="Node connection timeout", code=4400)
        except Exception as e:
            logging.getLogger("marzban").error(f"Node logs WS: Error connecting to node {node_id}: {e}")
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
    db: Session = Depends(get_db),
    admin: Admin = Depends(Admin.check_sudo_admin)
):
    """Retrieve a list of all nodes. Requires sudo admin privileges."""
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

    logging.getLogger("marzban").info(f'Node "{dbnode.name}" modified')
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

    logging.getLogger("marzban").info(f'Node "{dbnode.name}" deleted')
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
