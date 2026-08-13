from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.visit import VisitorVisitListResponse
from app.services.visit_service import VisitService

router = APIRouter(prefix="/visits", tags=["visits"])


@router.get("", response_model=VisitorVisitListResponse, summary="List recorded visitor visits")
def list_visits(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    items, total = VisitService.list_visits(db, skip=skip, limit=limit)
    return VisitorVisitListResponse(total=total, items=items)