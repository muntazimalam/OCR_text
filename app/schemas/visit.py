from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class VisitorVisitResponse(BaseModel):
    id: UUID
    ip_address: str
    user_agent: Optional[str] = None
    path: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accessed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VisitorVisitListResponse(BaseModel):
    total: int
    items: List[VisitorVisitResponse]