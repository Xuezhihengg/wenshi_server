from pydantic import BaseModel, Field

from app.schemas.common import OrmModel


class NotificationSettingsUpdate(BaseModel):
    system_enabled: bool | None = None
    push_enabled: bool | None = None
    daily_check_in: bool | None = None
    reading_complete: bool | None = None
    quiet_hours_enabled: bool | None = None
    quiet_start: str | None = Field(default=None, pattern='^([01]\\d|2[0-3]):[0-5]\\d$')
    quiet_end: str | None = Field(default=None, pattern='^([01]\\d|2[0-3]):[0-5]\\d$')


class NotificationSettingsOut(OrmModel):
    system_enabled: bool
    push_enabled: bool
    daily_check_in: bool
    reading_complete: bool
    quiet_hours_enabled: bool
    quiet_start: str
    quiet_end: str
