from typing import List, Optional
from pydantic import BaseModel, Field

class Plan(BaseModel):
    id: str
    name: str
    description: str
    price: float
    duration_days: int
    data_limit: Optional[int] = None  # None means unlimited
    stripe_price_id: Optional[str] = None
    features: List[str] = Field(default_factory=list)

class PlanResponse(Plan):
    """Response model for plan data, inherits all fields from Plan"""
    pass