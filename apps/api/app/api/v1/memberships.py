from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.membership import (
    CreateOrderRequest,
    CurrentMembershipOut,
    MockPaymentCallback,
    OrderOut,
    PlanOut,
)
from app.services import memberships as service

router = APIRouter(prefix='/memberships', tags=['memberships'])


@router.get('/plans', response_model=list[PlanOut])
async def plans():
    return service.plans()


@router.get('/current', response_model=CurrentMembershipOut)
async def current(user: CurrentUser):
    return CurrentMembershipOut(plan=user.membership_plan.value, status=user.membership_status.value, expires_at=user.membership_expires_at)


@router.post('/orders', response_model=OrderOut)
async def create_order(payload: CreateOrderRequest, db: DbSession, user: CurrentUser):
    return await service.create_order(db, user, payload.plan, payload.channel)


@router.get('/orders', response_model=list[OrderOut])
async def list_orders(db: DbSession, user: CurrentUser):
    return await service.list_orders(db, user)


@router.post('/mock-callback', response_model=OrderOut)
async def mock_callback(payload: MockPaymentCallback, db: DbSession):
    return await service.mock_payment_callback(db, payload.provider_order_id, payload.success)
