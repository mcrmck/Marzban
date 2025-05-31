from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class Plan(BaseModel):
    id: str
    name: str
    description: str
    price: float
    duration_days: int
    data_limit: Optional[int] = None  # in bytes, None means unlimited
    max_connections: int = 1
    stripe_price_id: Optional[str] = None  # Made optional with None as default
    features: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True