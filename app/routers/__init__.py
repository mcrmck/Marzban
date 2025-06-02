from fastapi import APIRouter

# Import the routers from specific modules
from .admin_panel import router as admin_panel_api_router
from .client_portal import router as client_portal_api_router
from .core import router as core_router


# Main API router that will be included in app/__init__.py
api_router = APIRouter()

# Include admin panel API routes under /api/admin
api_router.include_router(admin_panel_api_router, prefix="/admin", tags=["Admin Panel API"])

# Include client portal API routes under /api/portal
api_router.include_router(client_portal_api_router, prefix="/portal", tags=["Client Portal API"])

# Import and include core API routers
api_router.include_router(core_router, prefix="/core", tags=["Core"])

__all__ = ["api_router"]