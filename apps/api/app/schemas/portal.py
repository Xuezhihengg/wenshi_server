from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import OrmModel


class PortalVisitCreate(BaseModel):
    path: str = Field(default='/', max_length=255)
    language: str | None = Field(default=None, max_length=12)
    referrer: str | None = Field(default=None, max_length=1000)
    utm_source: str | None = Field(default=None, max_length=120)
    utm_medium: str | None = Field(default=None, max_length=120)
    utm_campaign: str | None = Field(default=None, max_length=160)
    session_id: str | None = Field(default=None, max_length=80)
    metadata: dict | None = None


class PortalVisitOut(OrmModel):
    id: str
    path: str
    language: str | None
    referrer: str | None
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    session_id: str | None
    created_at: datetime
