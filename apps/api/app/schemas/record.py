from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import OrmModel


class VerificationNoteIn(BaseModel):
    fulfilled: bool = True
    note: str = ''
    noted_at: datetime | None = None


class VerificationNoteUpdate(BaseModel):
    fulfilled: bool | None = None
    note: str | None = None
    noted_at: datetime | None = None


class VerificationNoteOut(OrmModel):
    id: str
    fulfilled: bool
    note: str
    noted_at: datetime
    created_at: datetime
    updated_at: datetime


class AIReadingTimelineItem(BaseModel):
    type: str
    label: str
    time_text: str
    detail: str | None = None


class AIReadingPoint(BaseModel):
    claim: str
    evidence: list[str] = Field(default_factory=list, max_length=2)
    explanation: str


class AIReadingOut(BaseModel):
    verdict: str
    expected_time_text: str | None = None
    timeline: list[AIReadingTimelineItem] = Field(default_factory=list)
    points: list[AIReadingPoint] = Field(default_factory=list, max_length=4)
    status: str = 'ready'
    generated_at: datetime
    model: str | None = None
    lang: str | None = None


class RecordCreate(BaseModel):
    id: str | None = None
    profile_id: str | None = None
    question: str = Field(min_length=1)
    hexagram_name: str | None = None
    changed_hexagram_name: str | None = None
    favorite: bool = False
    cast_at: datetime | None = None
    payload: dict[str, Any]


class RecordUpdate(BaseModel):
    profile_id: str | None = None
    question: str | None = None
    hexagram_name: str | None = None
    changed_hexagram_name: str | None = None
    favorite: bool | None = None
    cast_at: datetime | None = None
    payload: dict[str, Any] | None = None


class RecordOut(OrmModel):
    id: str
    profile_id: str | None
    question: str
    hexagram_name: str | None
    changed_hexagram_name: str | None
    favorite: bool
    cast_at: datetime
    payload: dict[str, Any]
    ai_reading_status: str
    notes: list[VerificationNoteOut] = []
    created_at: datetime
    updated_at: datetime


class RecordListItem(OrmModel):
    id: str
    profile_id: str | None
    question: str
    hexagram_name: str | None
    changed_hexagram_name: str | None
    favorite: bool
    cast_at: datetime
    latest_status: str
    created_at: datetime
