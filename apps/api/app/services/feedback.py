from fastapi import HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthProvider, Feedback, FeedbackType, User
from app.schemas.feedback import FeedbackCreate, PublicFeedbackCreate
from app.services.audit import write_audit_log

PORTAL_USER_EMAIL = 'portal@wenshi.local'
PORTAL_USER_NAME = 'Portal Visitor'
PUBLIC_FEEDBACK_RATE_LIMIT = 5
PUBLIC_FEEDBACK_RATE_WINDOW_SECONDS = 3600


async def create_feedback(db: AsyncSession, user: User, payload: FeedbackCreate) -> Feedback:
    feedback = Feedback(
        user_id=user.id,
        type=FeedbackType(payload.type),
        description=payload.description.strip(),
        screenshot_urls=payload.screenshot_urls,
        app_version=payload.app_version,
        platform=payload.platform,
        device_info=payload.device_info,
    )
    db.add(feedback)
    await db.flush()
    await write_audit_log(db, user.id, 'feedback.create', 'feedback', feedback.id, {'type': payload.type})
    await db.commit()
    await db.refresh(feedback)
    return feedback


async def create_public_feedback(db: AsyncSession, redis_client: Redis, request: Request, payload: PublicFeedbackCreate) -> Feedback:
    client_ip = _client_ip(request)
    await ensure_public_feedback_rate_limit(redis_client, client_ip)
    user = await ensure_portal_user(db)
    device_info = {
        'source': 'portal',
        'name': payload.name.strip() if payload.name else None,
        'email': payload.email.strip().lower() if payload.email else None,
        'language': payload.language,
        'user_agent': request.headers.get('user-agent'),
        'client_ip': client_ip,
    }
    feedback = Feedback(
        user_id=user.id,
        type=FeedbackType(payload.type),
        description=payload.description.strip(),
        screenshot_urls=[],
        app_version='portal',
        platform='web',
        device_info=device_info,
    )
    db.add(feedback)
    await db.flush()
    await write_audit_log(db, user.id, 'feedback.public_create', 'feedback', feedback.id, {'type': payload.type, 'source': 'portal'})
    await db.commit()
    await db.refresh(feedback)
    return feedback


async def ensure_portal_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).where(User.email == PORTAL_USER_EMAIL))
    if user:
        if user.display_name != PORTAL_USER_NAME:
            user.display_name = PORTAL_USER_NAME
        return user
    user = User(
        email=PORTAL_USER_EMAIL,
        display_name=PORTAL_USER_NAME,
        register_provider=AuthProvider.email,
        profile_completed=False,
    )
    db.add(user)
    await db.flush()
    return user


async def ensure_public_feedback_rate_limit(redis_client: Redis, client_ip: str) -> None:
    key = f'public_feedback:rate:{client_ip}'
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, PUBLIC_FEEDBACK_RATE_WINDOW_SECONDS)
    if count > PUBLIC_FEEDBACK_RATE_LIMIT:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='Too many feedback submissions. Please try again later.')


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get('x-forwarded-for')
    if forwarded_for:
        return forwarded_for.split(',', 1)[0].strip() or 'unknown'
    return request.client.host if request.client else 'unknown'
