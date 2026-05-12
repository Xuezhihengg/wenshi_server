from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import OrmModel


class PlanOut(BaseModel):
    plan: str
    title: str
    price_cents: int
    currency: str = 'CNY'
    privileges: list[str]


class CurrentMembershipOut(BaseModel):
    plan: str
    status: str
    expires_at: datetime | None


class CreateOrderRequest(BaseModel):
    plan: str = Field(pattern='^(monthly|yearly)$')
    channel: str = Field(pattern='^(apple|wechat|alipay|mock)$')


class MockPaymentCallback(BaseModel):
    provider_order_id: str
    success: bool = True


class OrderOut(OrmModel):
    id: str
    plan: str
    channel: str
    status: str
    amount_cents: int
    currency: str
    provider_order_id: str | None
    paid_at: datetime | None
    created_at: datetime
