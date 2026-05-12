from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import OrmModel


class ProfileBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    relation: str = Field(min_length=1, max_length=40)
    gender: str = Field(pattern='^(男|女|未填写)$')
    birthday: str = Field(min_length=1, max_length=120)
    avatar_url: str | None = None


class ProfileCreate(ProfileBase):
    is_selected: bool = False


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    relation: str | None = Field(default=None, min_length=1, max_length=40)
    gender: str | None = Field(default=None, pattern='^(男|女|未填写)$')
    birthday: str | None = Field(default=None, min_length=1, max_length=120)
    avatar_url: str | None = None
    is_selected: bool | None = None


class ProfileOut(OrmModel):
    id: str
    name: str
    relation: str
    gender: str
    birthday: str
    avatar_url: str | None
    is_selected: bool
    created_at: datetime
    updated_at: datetime
