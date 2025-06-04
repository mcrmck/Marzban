from fastapi import APIRouter

router = APIRouter()

# Import and include client portal specific routers
from . import (
    account,
    auth,
    subscription,
)

# Include all client portal routers
router.include_router(auth.router)
router.include_router(account.router)
router.include_router(subscription.router)

__all__ = ["router"]