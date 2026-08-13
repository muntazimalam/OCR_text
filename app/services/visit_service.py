import ipaddress
from typing import Optional
from uuid import UUID
from fastapi import Request
from sqlalchemy.orm import Session

from app.core import database as db_module
from app.core.config import settings
from app.core.logging import logger
from app.models.visit import VisitorVisit

# Human-facing pages recorded as "visits" — API endpoints, uploads and
# static assets are excluded to keep the table meaningful.
TRACKED_PATHS = ("/", "/docs")


def _is_global_ip(ip: str) -> bool:
    """True only for public, routable IPs (geo lookup is pointless for LAN/dev traffic)."""
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


class VisitService:
    @staticmethod
    def get_client_ip(request: Request) -> Optional[str]:
        """Best-effort client IP, preferring the first X-Forwarded-For hop (proxies)."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first_hop = forwarded.split(",")[0].strip()
            if first_hop:
                return first_hop
        return request.client.host if request.client else None

    @staticmethod
    def record_page_visit(request: Request) -> Optional[UUID]:
        """
        Synchronously persists a page visit (IP, user agent, path, access time)
        so the visitor is recorded even if later geo enrichment fails.
        """
        ip = VisitService.get_client_ip(request)
        if not ip:
            return None

        user_agent = (request.headers.get("user-agent") or "").strip()[:512] or None

        db = db_module.SessionLocal()
        try:
            visit = VisitorVisit(
                ip_address=ip,
                user_agent=user_agent,
                path=request.url.path,
            )
            db.add(visit)
            db.commit()
            db.refresh(visit)
            return visit.id
        except Exception as exc:
            logger.error("visit_record_failed", error=str(exc))
            db.rollback()
            return None
        finally:
            db.close()

    @staticmethod
    async def enrich_with_location(visit_id: UUID) -> None:
        """
        Fire-and-forget: resolves approximate location for a recorded visit via
        the free ip-api.com endpoint and updates the row. Fails silently —
        location fields simply stay null for local/private addresses.
        """
        if not settings.GEO_LOOKUP_ENABLED:
            return

        db = db_module.SessionLocal()
        try:
            visit = db.query(VisitorVisit).filter(VisitorVisit.id == visit_id).first()
            if not visit or not _is_global_ip(visit.ip_address):
                return

            import httpx

            url = settings.GEO_LOOKUP_URL.format(ip=visit.ip_address)
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(
                    url,
                    params={"fields": "status,country,regionName,city,lat,lon"},
                )
                data = resp.json()

            if data.get("status") == "success":
                visit.country = data.get("country")
                visit.region = data.get("regionName")
                visit.city = data.get("city")
                visit.latitude = data.get("lat")
                visit.longitude = data.get("lon")
                db.commit()
                logger.info("visit_location_resolved", visit_id=str(visit_id), ip=visit.ip_address)
        except Exception as exc:
            logger.warning("visit_geo_lookup_failed", visit_id=str(visit_id), error=str(exc)[:200])
        finally:
            db.close()

    @staticmethod
    def list_visits(db: Session, skip: int = 0, limit: int = 50):
        total = db.query(VisitorVisit).count()
        items = (
            db.query(VisitorVisit)
            .order_by(VisitorVisit.accessed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total