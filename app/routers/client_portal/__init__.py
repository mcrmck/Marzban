from fastapi import APIRouter

router = APIRouter()

# Import and include client portal specific routers
from . import (
    auth,
    main,
    subscription,
)

# Include all client portal routers
router.include_router(auth.router)
router.include_router(main.router)
router.include_router(subscription.router)

__all__ = ["router"]