from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIReadingUsageEvent, MembershipPlan, MembershipStatus, Profile, User

SHANGHAI_TZ = ZoneInfo('Asia/Shanghai')


@dataclass(frozen=True)
class PlanLimits:
    profile_limit: int | None
    ai_daily_limit: int | None


PLAN_LIMITS: dict[MembershipPlan, PlanLimits] = {
    MembershipPlan.trial: PlanLimits(profile_limit=5, ai_daily_limit=2),
    MembershipPlan.monthly: PlanLimits(profile_limit=20, ai_daily_limit=20),
    MembershipPlan.yearly: PlanLimits(profile_limit=None, ai_daily_limit=None),
}


def effective_plan(user: User, now: datetime | None = None) -> MembershipPlan:
    current = now or datetime.now(UTC)
    if (
        user.membership_status == MembershipStatus.active
        and user.membership_plan in {MembershipPlan.monthly, MembershipPlan.yearly}
        and (user.membership_expires_at is None or user.membership_expires_at > current)
    ):
        return user.membership_plan
    return MembershipPlan.trial


def _quota_error(code: str, limit: int, used: int, plan: MembershipPlan) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            'code': code,
            'limit': limit,
            'used': used,
            'plan': plan.value,
        },
    )


async def assert_profile_quota(db: AsyncSession, user: User) -> None:
    plan = effective_plan(user)
    limit = PLAN_LIMITS[plan].profile_limit
    if limit is None:
        return
    used = await db.scalar(select(func.count()).select_from(Profile).where(Profile.user_id == user.id)) or 0
    if used >= limit:
        raise _quota_error('profile_limit_exceeded', limit, used, plan)


def shanghai_day_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    local_now = (now or datetime.now(UTC)).astimezone(SHANGHAI_TZ)
    start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


async def assert_ai_quota(db: AsyncSession, user: User, now: datetime | None = None) -> tuple[MembershipPlan, int]:
    plan = effective_plan(user, now)
    limit = PLAN_LIMITS[plan].ai_daily_limit
    if limit is None:
        return plan, 0
    start, end = shanghai_day_window(now)
    used = await db.scalar(
        select(func.count()).select_from(AIReadingUsageEvent).where(
            AIReadingUsageEvent.user_id == user.id,
            AIReadingUsageEvent.used_at >= start,
            AIReadingUsageEvent.used_at < end,
        )
    ) or 0
    if used >= limit:
        raise _quota_error('ai_quota_exceeded', limit, used, plan)
    return plan, used


async def record_ai_usage(db: AsyncSession, user: User, record_id: str, plan: MembershipPlan, lang: str, used_at: datetime | None = None) -> None:
    db.add(
        AIReadingUsageEvent(
            user_id=user.id,
            record_id=record_id,
            plan=plan,
            used_at=used_at or datetime.now(UTC),
            lang=lang,
        )
    )
