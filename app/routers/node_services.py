from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db import crud
from app.models.node_service import (
    NodeServiceConfigurationResponse,
    NodeServiceConfigurationCreate,
    NodeServiceConfigurationUpdate
)
from app.db import get_db
from app.db.models import NodeServiceConfiguration
from app.xray import xray  # This import should now work correctly
from app.xray.node import XRayNode
from app.xray import operations
import logging
from config import XRAY_CONFIG_PATH
# from app.dependencies import get_current_active_admin_user # Authentication

logger = logging.getLogger("marzban.node_services")

router = APIRouter(
    prefix="/api",
    tags=["Node Services"]
)

@router.post(
    "/nodes/{node_id}/services/",
    response_model=NodeServiceConfigurationResponse,
    status_code=status.HTTP_201_CREATED
)
def create_service_for_node(
    node_id: int,
    service_in: NodeServiceConfigurationCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new service configuration for a specific node.
    Triggers a node reconfiguration.
    """
    db_node = crud.get_node_by_id(db, node_id)
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Create new service configuration using CRUD function
    try:
        db_service = crud.create_with_node(db, obj_in=service_in, node_id=node_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Trigger node reconfiguration
    try:
        # Use the global config instance
        xray.config.node_api_port = db_node.api_port
        users_on_node = crud.get_users_by_active_node_id(db, node_id)
        node_specific_xray_config_obj = xray.config.build_node_config(db_node, users_on_node)

        # Get node instance and restart with new config
        node_instance = operations.connect_node(node_id)
        if node_instance and node_instance.connected:
            node_instance.restart(node_specific_xray_config_obj)
            logger.info(f"Successfully reconfigured node {db_node.name} after service creation")
        else:
            logger.warning(f"Node {db_node.name} not connected, skipping reconfiguration")
    except Exception as e:
        logger.error(f"Failed to reconfigure node {db_node.name} after service creation: {e}", exc_info=True)
        # Don't raise an error here, as the service was created successfully
        # Just log the error and continue

    return db_service

@router.get(
    "/nodes/{node_id}/services/",
    response_model=List[NodeServiceConfigurationResponse]
)
def read_services_for_node(
    node_id: int,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve all service configurations for a specific node.
    """
    db_node = crud.get_node_by_id(db, node_id)
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")
    services = crud.get_services_for_node(db, node_id=node_id, skip=skip, limit=limit)
    return services

@router.get(
    "/nodes/{node_id}/services/{service_id}",
    response_model=NodeServiceConfigurationResponse
)
def read_single_service(
    node_id: int,
    service_id: int,
    db: Session = Depends(get_db)
):
    """
    Retrieve a specific service configuration by its ID, ensuring it belongs to the specified node.
    """
    service = crud.get_service_for_node(db, id=service_id, node_id=node_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found or does not belong to this node")
    return service

@router.put(
    "/nodes/{node_id}/services/{service_id}",
    response_model=NodeServiceConfigurationResponse
)
def update_service_on_node(
    node_id: int, # Ensure service belongs to this node
    service_id: int,
    service_in: NodeServiceConfigurationUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a service configuration on a specific node.
    Triggers a node reconfiguration.
    """
    db_service = crud.get_service_for_node(db, id=service_id, node_id=node_id)
    if not db_service:
        raise HTTPException(status_code=404, detail="Service not found or does not belong to this node")

    # TODO: Handle xray_inbound_tag updates carefully if it needs to remain unique per node.

    updated_service = crud.update(db, db_obj=db_service, obj_in=service_in)

    # TODO: Trigger node reconfiguration logic
    # xray_operations.reconfigure_node(db, node_id=node_id)

    return updated_service

@router.delete(
    "/nodes/{node_id}/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_service_from_node(
    node_id: int,
    service_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a service configuration from a specific node.
    Triggers a node reconfiguration.
    """
    db_service = crud.get_service_for_node(db, id=service_id, node_id=node_id)
    if not db_service:
        raise HTTPException(status_code=404, detail="Service not found or does not belong to this node")

    crud.remove(db, id=service_id)

    # TODO: Trigger node reconfiguration logic
    # xray_operations.reconfigure_node(db, node_id=node_id)

    return {"ok": True}

# Remember to include this router in your main FastAPI app (e.g., in app/main.py or app/routers/__init__.py)
# from . import node_services
# app.include_router(node_services.router, prefix="/api/v1") # Or your chosen prefix