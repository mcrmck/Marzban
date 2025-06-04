from typing import Optional
from sqlalchemy.orm import Session
from app.db import crud
from app.portal.models.plan import Plan

def get_plan_by_id(db: Session, plan_id: str) -> Optional[Plan]:
    """Get a plan by its ID from the database."""
    return crud.get_plan_by_id(db, plan_id)