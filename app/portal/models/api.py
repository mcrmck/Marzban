from pydantic import BaseModel
from typing import List, Optional
from app.models.user import UserResponse
from app.models.node import NodeResponse

class ClientLoginRequest(BaseModel):
    """Request model for client login."""
    account_number: str

class TokenResponse(BaseModel):
    """Response model for authentication token."""
    access_token: str
    token_type: str = "bearer"  # Default to bearer token type

class PortalAccountDetailsResponse(BaseModel):
    """Response model for client portal account details."""
    user: UserResponse
    active_node: Optional[NodeResponse] = None
    available_nodes: List[NodeResponse]
    stripe_public_key: Optional[str]
    mock_stripe_payment: bool
    frontend_url: Optional[str]
    stripe_enabled: bool  # Added for convenience in frontend

    class Config:
        from_attributes = True