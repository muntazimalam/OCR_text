import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, Uuid

from app.core.database import Base


class VisitorVisit(Base):
    __tablename__ = "visitor_visits"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip_address = Column(String(45), nullable=False, index=True)
    user_agent = Column(String(512), nullable=True)
    path = Column(String(255), nullable=True)
    country = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    accessed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)