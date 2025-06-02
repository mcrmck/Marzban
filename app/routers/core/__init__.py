from fastapi import APIRouter

router = APIRouter()

# Import and include core API routers
from . import (
    core,
    user,
    home,
)

# Include all core routers
router.include_router(core.router)
router.include_router(user.router)
router.include_router(home.router)

__all__ = ["router"]