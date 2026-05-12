from fastapi import APIRouter, Request, status

from app.api.deps import DbSession
from app.core.redis import get_redis
from app.schemas.feedback import FeedbackOut, PublicFeedbackCreate
from app.schemas.portal import PortalVisitCreate, PortalVisitOut
from app.services import feedback as service
from app.services import portal as portal_service

router = APIRouter(prefix='/public', tags=['public'])


@router.post('/feedback', response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def create_public_feedback(payload: PublicFeedbackCreate, request: Request, db: DbSession):
    redis_client = get_redis()
    try:
        return await service.create_public_feedback(db, redis_client, request, payload)
    finally:
        await redis_client.aclose()


@router.post('/portal-visit', response_model=PortalVisitOut, status_code=status.HTTP_201_CREATED)
async def create_portal_visit(payload: PortalVisitCreate, request: Request, db: DbSession):
    return await portal_service.create_portal_visit(db, request, payload)
