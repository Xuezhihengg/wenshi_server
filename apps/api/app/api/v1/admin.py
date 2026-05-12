from fastapi import APIRouter, Query

from app.api.deps import CurrentAdmin, DbSession
from app.schemas.admin import (
    AdminAnalytics,
    AdminFeedbackItem,
    AdminFeedbackPage,
    AdminFeedbackStarRequest,
    AdminFeedbackStatusRequest,
    AdminLogPage,
    AdminOrderItem,
    AdminPortalTraffic,
    AdminRecordItem,
    AdminStats,
    AdminUserItem,
)
from app.schemas.auth import AdminLoginRequest, TokenPair
from app.services import admin as service
from app.services.auth import admin_login
from app.services.logs import query_logs

router = APIRouter(prefix='/admin', tags=['admin'])


@router.post('/login', response_model=TokenPair)
async def login(payload: AdminLoginRequest, db: DbSession):
    return await admin_login(db, str(payload.username), payload.password)


@router.get('/stats', response_model=AdminStats)
async def stats(db: DbSession, _: CurrentAdmin):
    return await service.stats(db)


@router.get('/users', response_model=list[AdminUserItem])
async def users(db: DbSession, _: CurrentAdmin, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return await service.users(db, limit, offset)


@router.get('/orders', response_model=list[AdminOrderItem])
async def orders(db: DbSession, _: CurrentAdmin, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return await service.orders(db, limit, offset)


@router.get('/records', response_model=list[AdminRecordItem])
async def records(db: DbSession, _: CurrentAdmin, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return await service.records(db, limit, offset)


@router.get('/feedback', response_model=AdminFeedbackPage)
async def feedback(
    db: DbSession,
    _: CurrentAdmin,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=120),
    feedback_type: str | None = Query(None, pattern='^(all|bug|feature|experience|other)$'),
    feedback_status: str | None = Query(None, pattern='^(all|open|reviewing|resolved|ignored)$'),
    has_images: bool | None = Query(None),
    starred: bool | None = Query(None),
):
    return await service.feedback(db, limit, offset, q, feedback_type, feedback_status, has_images, starred)


@router.patch('/feedback/{feedback_id}/star', response_model=AdminFeedbackItem)
async def star_feedback(feedback_id: str, payload: AdminFeedbackStarRequest, db: DbSession, admin_user: CurrentAdmin):
    return await service.set_feedback_starred(db, feedback_id, payload.starred, admin_user)


@router.patch('/feedback/{feedback_id}/status', response_model=AdminFeedbackItem)
async def update_feedback_status(feedback_id: str, payload: AdminFeedbackStatusRequest, db: DbSession, admin_user: CurrentAdmin):
    return await service.set_feedback_status(db, feedback_id, payload.status, admin_user)


@router.get('/analytics', response_model=AdminAnalytics)
async def analytics(db: DbSession, _: CurrentAdmin, days: int = Query(14, ge=7, le=60)):
    return await service.analytics(db, days)


@router.get('/portal-traffic', response_model=AdminPortalTraffic)
async def portal_traffic(db: DbSession, _: CurrentAdmin, days: int = Query(14, ge=7, le=90)):
    return await service.portal_traffic(db, days)


@router.get('/logs', response_model=AdminLogPage)
async def logs(
    _: CurrentAdmin,
    date: str | None = Query(None, pattern=r'^\d{4}-\d{2}-\d{2}$'),
    level: str | None = Query(None, pattern='^(debug|info|warning|error|critical)$'),
    q: str | None = Query(None, max_length=200),
    request_id: str | None = Query(None, max_length=120),
    limit: int = Query(200, ge=1, le=1000),
):
    return await query_logs(date, level, q, request_id, limit)
