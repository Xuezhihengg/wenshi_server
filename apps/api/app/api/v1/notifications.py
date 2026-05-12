from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.notification import NotificationSettingsOut, NotificationSettingsUpdate
from app.services.notifications import get_or_create_settings, update_settings

router = APIRouter(prefix='/notifications', tags=['notifications'])


@router.get('/settings', response_model=NotificationSettingsOut)
async def get_settings(db: DbSession, user: CurrentUser):
    return await get_or_create_settings(db, user)


@router.patch('/settings', response_model=NotificationSettingsOut)
async def patch_settings(payload: NotificationSettingsUpdate, db: DbSession, user: CurrentUser):
    return await update_settings(db, user, payload)
