from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ApiMessage(BaseModel):
    message: str


class Page(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class ReadyResponse(BaseModel):
    status: str
    postgres: bool
    redis: bool


class AuditLogOut(OrmModel):
    id: str
    actor_user_id: str | None
    action: str
    target_type: str | None
    target_id: str | None
    metadata_json: dict | None
    created_at: datetime
