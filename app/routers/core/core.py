import asyncio
import json
import time

import commentjson
from fastapi import APIRouter, Depends, HTTPException, WebSocket
from starlette.websockets import WebSocketDisconnect

from app import xray
from app.db import Session, get_db
from app.models.admin import Admin
from app.models.core import CoreStats
from app.utils import responses

router = APIRouter(tags=["Core"], prefix="/api", responses={401: responses._401})

@router.get("/core", response_model=CoreStats)
def get_core_stats(admin: Admin = Depends(Admin.get_current)):
    """Retrieve panel status."""
    return CoreStats(
        version="Panel v1.0 (Decoupled)",
        started=True,
        logs_websocket=""
    )

@router.post("/core/restart", responses={403: responses._403})
def restart_all_nodes(admin: Admin = Depends(Admin.check_sudo_admin)):
    """Restart all connected Xray nodes."""
    config_for_nodes = xray.config.include_db_users()

    restarted_nodes = []
    failed_nodes = []

    for node_id, node in list(xray.nodes.items()):
        if node.connected:
            try:
                print(f"Attempting to restart node ID: {node_id}")
                xray.operations.restart_node(node_id, config_for_nodes)
                restarted_nodes.append(node_id)
            except Exception as e:
                print(f"Failed to restart node ID {node_id}: {e}")
                failed_nodes.append({"node_id": node_id, "error": str(e)})
        else:
            print(f"Skipping restart for disconnected node ID: {node_id}")

    return {"detail": "Restart command issued to all connected nodes.", "restarted": restarted_nodes, "failed": failed_nodes}

@router.get("/core/config", responses={403: responses._403})
def get_default_template_config(admin: Admin = Depends(Admin.check_sudo_admin)) -> dict:
    """Get the current default/template Xray configuration for nodes."""
    return dict(xray.config)

@router.put("/core/config", responses={403: responses._403})
def modify_default_template_config(
    payload: dict, admin: Admin = Depends(Admin.check_sudo_admin)
) -> dict:
    """Modify the in-memory default/template Xray configuration and restart all connected nodes."""
    try:
        # Update the global config instance with the new template
        xray.config.update(payload)
        # Ensure API port is preserved
        xray.config["api"] = xray.config.get("api", {})
        xray.config["api"]["port"] = xray.config.api_port
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    # Generate a full config with users based on the updated template
    config_for_nodes = xray.config.include_db_users()

    # Restart all connected nodes to apply the new template-based config
    restarted_nodes = []
    failed_nodes = []
    for node_id, node in list(xray.nodes.items()):
        if node.connected:
            try:
                print(f"Attempting to restart node ID {node_id} with new template-based config.")
                xray.operations.restart_node(node_id, config_for_nodes)
                restarted_nodes.append(node_id)
            except Exception as e:
                print(f"Failed to restart node ID {node_id} with new template: {e}")
                failed_nodes.append({"node_id": node_id, "error": str(e)})
        else:
            print(f"Skipping restart for disconnected node ID: {node_id}")

    # Update hosts based on the new xray.config template's inbounds
    if hasattr(xray, 'hosts') and callable(getattr(xray.hosts, 'update', None)):
        xray.hosts.update()
    else:
        print("Warning: xray.hosts.update() not found or not callable. Host list may be stale.")

    return {
        "detail": "Default template config updated. Restart command issued to all connected nodes.",
        "new_template_preview": dict(xray.config),
        "restarted_nodes": restarted_nodes,
        "failed_nodes": failed_nodes
    }
