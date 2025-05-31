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
from app.xray import XRayConfig

router = APIRouter(tags=["Core"], prefix="/api", responses={401: responses._401})



@router.get("/core", response_model=CoreStats)  # Keep CoreStats or create a new PanelStats model
def get_core_stats(admin: Admin = Depends(Admin.get_current)):
    """Retrieve panel status."""
    # xray.core no longer exists.
    # The concept of a single "core version" and "core started" for the panel is different now.
    # The panel itself is "started" if this endpoint is reachable.
    # We can return a static version for the panel or a general status.
    # The 'logs_websocket' for a central core is no longer applicable.
    return CoreStats(
        version="Panel v1.0 (Decoupled)", # Placeholder version, can be dynamic later
        started=True, # If the API is up, the panel is "started"
        # logs_websocket=None # Or remove this field from CoreStats model if it's always None
        # Alternatively, if CoreStats requires logs_websocket:
        logs_websocket="" # Empty string if the field must exist but is not applicable
    )


@router.post("/core/restart", responses={403: responses._403})
def restart_all_nodes(admin: Admin = Depends(Admin.check_sudo_admin)): # Renamed for clarity
    """Restart all connected Xray nodes."""
    # The global xray.config (our template) is used by include_db_users
    # to generate a full config with current users.
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
def get_default_template_config(admin: Admin = Depends(Admin.check_sudo_admin)) -> dict: # Renamed for clarity
    """Get the current default/template Xray configuration for nodes."""
    # xray.config is our XRayConfig object holding the template.
    # XRayConfig is a subclass of dict, so it can be returned directly.
    return dict(xray.config) # Return a copy as a plain dict


@router.put("/core/config", responses={403: responses._403})
def modify_default_template_config( # Renamed for clarity
    payload: dict, admin: Admin = Depends(Admin.check_sudo_admin)
) -> dict:
    """Modify the in-memory default/template Xray configuration and restart all connected nodes."""
    try:
        # Create a new XRayConfig instance from the payload to validate it.
        # Use the api_port from the current xray.config template, as this isn't changed here.
        new_template_config = XRayConfig(config_dict=payload, api_port=xray.config.api_port)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    # Update the global in-memory xray.config object to this new template.
    xray.config = new_template_config

    # Note: Persisting this template to a file is not done here.
    # If persistence is needed, it would be an additional step.
    # For example:
    # with open("default_xray_template.json", "w") as f:
    #     f.write(xray.config.to_json(indent=4))

    # Generate a full config with users based on the NEW template
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
    # This assumes xray.hosts.update() reads from xray.config
    if hasattr(xray, 'hosts') and callable(getattr(xray.hosts, 'update', None)):
        xray.hosts.update()
    else:
        print("Warning: xray.hosts.update() not found or not callable. Host list may be stale.")


    return {"detail": "Default template config updated. Restart command issued to all connected nodes.",
            "new_template_preview": dict(xray.config),
            "restarted_nodes": restarted_nodes,
            "failed_nodes": failed_nodes
            }
