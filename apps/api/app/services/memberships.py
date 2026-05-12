from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MembershipPlan, MembershipStatus, Order, OrderChannel, OrderStatus, User
from app.providers.payment import payment_provider

PLAN_CONFIG = {
    MembershipPlan.trial: {'title': '体验用户', 'price_cents': 0, 'privileges': ['基础起卦', '本地记录', '基础档案']},
    MembershipPlan.monthly: {'title': '月度会员', 'price_cents': 1800, 'privileges': ['云端同步', '高级统计', '更多档案', '优先功能']},
    MembershipPlan.yearly: {'title': '年度会员', 'price_cents': 18800, 'privileges': ['月度全部权益', '年度优惠', '长期记录归档', '会员标识']},
}


def plans() -> list[dict]:
    return [{'plan': key.value, 'currency': 'CNY', **value} for key, value in PLAN_CONFIG.items()]


async def create_order(db: AsyncSession, user: User, plan: str, channel: str) -> Order:
    plan_enum = MembershipPlan(plan)
    if plan_enum == MembershipPlan.trial:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Trial plan is free')
    amount = PLAN_CONFIG[plan_enum]['price_cents']
    intent = await payment_provider.create_intent(channel, amount, 'CNY')
    order = Order(user_id=user.id, plan=plan_enum, channel=OrderChannel(channel), status=OrderStatus.pending, amount_cents=amount, currency='CNY', provider_order_id=intent.provider_order_id, raw_payload=intent.raw_payload)
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


async def apply_paid_order(db: AsyncSession, order: Order) -> None:
    user = await db.get(User, order.user_id)
    if not user:
        return
    order.status = OrderStatus.paid
    order.paid_at = datetime.now(UTC)
    user.membership_plan = order.plan
    user.membership_status = MembershipStatus.active
    days = 31 if order.plan == MembershipPlan.monthly else 366
    base = user.membership_expires_at if user.membership_expires_at and user.membership_expires_at > datetime.now(UTC) else datetime.now(UTC)
    user.membership_expires_at = base + timedelta(days=days)


async def mock_payment_callback(db: AsyncSession, provider_order_id: str, success: bool) -> Order:
    order = await db.scalar(select(Order).where(Order.provider_order_id == provider_order_id))
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Order not found')
    if success:
        await apply_paid_order(db, order)
    else:
        order.status = OrderStatus.failed
    await db.commit()
    await db.refresh(order)
    return order


async def list_orders(db: AsyncSession, user: User) -> list[Order]:
    return list((await db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc()))).all())
