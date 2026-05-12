from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import OrmModel


class FeedbackCreate(BaseModel):
    type: str = Field(pattern='^(bug|feature|experience|other)$')
    description: str = Field(min_length=6, max_length=4000)
    screenshot_urls: list[str] = Field(default_factory=list, max_length=4)
    app_version: str | None = Field(default=None, max_length=80)
    platform: str | None = Field(default=None, max_length=40)
    device_info: dict | None = None


class PublicFeedbackCreate(BaseModel):
    type: str = Field(pattern='^(bug|feature|experience|other)$')
    description: str = Field(min_length=6, max_length=4000)
    name: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, max_length=12)


class FeedbackOut(OrmModel):
    id: str
    user_id: str
    type: str
    status: str
    description: str
    screenshot_urls: list[str]
    app_version: str | None
    platform: str | None
    device_info: dict | None
    created_at: datetime
