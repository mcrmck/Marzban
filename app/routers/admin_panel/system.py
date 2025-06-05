from typing import Dict, List, Union

from fastapi import APIRouter, Depends, HTTPException

from app import xray
from app.version import __version__
from app.db import Session, crud, get_db
from app.models.admin import Admin
from app.db.models import NodeServiceConfiguration
from app.models.node_service import NodeServiceConfigurationResponse
from app.models.system import SystemStats
from app.models.user import UserStatus
from app.utils import responses
from app.utils.system import cpu_usage, memory_usage, realtime_bandwidth

router = APIRouter(tags=["System"], responses={401: responses._401})


@router.get("/system", response_model=SystemStats)
def get_system_stats(
    db: Session = Depends(get_db), admin: Admin = Depends(Admin.get_current)
):
    """Fetch system stats including memory, CPU, and user metrics."""
    mem = memory_usage()
    cpu = cpu_usage()
    system = crud.get_system_usage(db)
    dbadmin: Union[Admin, None] = crud.get_admin(db, admin.username)

    total_user = crud.get_users_count(db, admin=dbadmin if not admin.is_sudo else None)
    users_active = crud.get_users_count(
        db, status=UserStatus.active, admin=dbadmin if not admin.is_sudo else None
    )
    users_disabled = crud.get_users_count(
        db, status=UserStatus.disabled, admin=dbadmin if not admin.is_sudo else None
    )
    users_on_hold = crud.get_users_count(
        db, status=UserStatus.on_hold, admin=dbadmin if not admin.is_sudo else None
    )
    users_expired = crud.get_users_count(
        db, status=UserStatus.expired, admin=dbadmin if not admin.is_sudo else None
    )
    users_limited = crud.get_users_count(
        db, status=UserStatus.limited, admin=dbadmin if not admin.is_sudo else None
    )
    online_users = crud.count_online_users(db, 24)
    realtime_bandwidth_stats = realtime_bandwidth()

    return SystemStats(
        version=__version__,
        mem_total=mem.total,
        mem_used=mem.used,
        cpu_cores=cpu.cores,
        cpu_usage=cpu.percent,
        total_user=total_user,
        users_active=users_active,
        users_disabled=users_disabled,
        users_on_hold=users_on_hold,
        users_expired=users_expired,
        users_limited=users_limited,
        online_users=online_users,
        incoming_bandwidth=system.downlink if system else 0,
        outgoing_bandwidth=system.uplink if system else 0,
        incoming_bandwidth_speed=realtime_bandwidth_stats.incoming_bytes,
        outgoing_bandwidth_speed=realtime_bandwidth_stats.outgoing_bytes
    )


@router.post("/system/nodes/restart-all", responses={403: responses._403})
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


@router.get("/system/xray-template-config", responses={403: responses._403})
def get_default_template_config(admin: Admin = Depends(Admin.check_sudo_admin)) -> dict:
    """Get the current default/template Xray configuration for nodes."""
    return dict(xray.config)


@router.put("/system/xray-template-config", responses={403: responses._403})
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
