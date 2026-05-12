from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NotificationSetting, User
from app.schemas.notification import NotificationSettingsUpdate


async def get_or_create_settings(db: AsyncSession, user: User) -> NotificationSetting:
    settings = await db.scalar(select(NotificationSetting).where(NotificationSetting.user_id == user.id))
    if settings:
        return settings
    settings = NotificationSetting(user_id=user.id)
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return settings


async def update_settings(db: AsyncSession, user: User, payload: NotificationSettingsUpdate) -> NotificationSetting:
    settings = await get_or_create_settings(db, user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    if not settings.system_enabled:
        settings.push_enabled = False
    if not settings.push_enabled:
        settings.daily_check_in = False
        settings.reading_complete = False
        settings.quiet_hours_enabled = False
    await db.commit()
    await db.refresh(settings)
    return settings
