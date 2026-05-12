import hashlib

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import PortalVisit
from app.schemas.portal import PortalVisitCreate


async def create_portal_visit(db: AsyncSession, request: Request, payload: PortalVisitCreate) -> PortalVisit:
    visit = PortalVisit(
        path=_clean_path(payload.path),
        language=payload.language,
        referrer=payload.referrer,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        user_agent=request.headers.get('user-agent'),
        ip_hash=_ip_hash(_client_ip(request)),
        session_id=payload.session_id,
        metadata_json=payload.metadata,
    )
    db.add(visit)
    await db.commit()
    await db.refresh(visit)
    return visit


def _clean_path(path: str) -> str:
    cleaned = path.strip() or '/'
    if not cleaned.startswith('/'):
        cleaned = f'/{cleaned}'
    return cleaned[:255]


def _ip_hash(client_ip: str) -> str | None:
    if not client_ip or client_ip == 'unknown':
        return None
    settings = get_settings()
    return hashlib.sha256(f'{settings.jwt_secret}:{client_ip}'.encode()).hexdigest()


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get('x-forwarded-for')
    if forwarded_for:
        return forwarded_for.split(',', 1)[0].strip() or 'unknown'
    return request.client.host if request.client else 'unknown'
