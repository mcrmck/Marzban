from fastapi import APIRouter

router = APIRouter()

# Import and include admin panel specific routers
from . import (
    admin,
    system,
    node,
    node_services,
)

# Include all admin panel routers
router.include_router(admin.router)
router.include_router(system.router)
router.include_router(node.router)
router.include_router(node_services.router)

__all__ = ["router"]