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
# from app.dependencies import get_current_active_admin_user # Authentication

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

    # Create new service configuration
    db_service = NodeServiceConfiguration(
        node_id=node_id,
        **service_in.model_dump()
    )
    db.add(db_service)
    db.commit()
    db.refresh(db_service)

    # TODO: Trigger node reconfiguration logic (e.g., call a method on the node object or a service)
    # This might involve:
    # 1. Generating the new Xray config for db_node with all its services.
    # 2. Pushing this config to the remote Xray instance via ReSTXRayNode.start() or restart().
    # Example: xray_operations.reconfigure_node(db, node_id=node_id)

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