from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Feedback,
    FeedbackStatus,
    FortuneRecord,
    MembershipPlan,
    Order,
    OrderStatus,
    PortalVisit,
    Profile,
    User,
    VerificationNote,
)
from app.schemas.admin import (
    AdminAnalytics,
    AdminDailyPoint,
    AdminDistributionItem,
    AdminFeedbackAnalytics,
    AdminFeedbackItem,
    AdminFeedbackPage,
    AdminOrderItem,
    AdminPortalDailyPoint,
    AdminPortalTraffic,
    AdminRecordItem,
    AdminRevenueSummary,
    AdminStats,
    AdminUserAnalytics,
    AdminUserItem,
)
from app.services.audit import write_audit_log


async def stats(db: AsyncSession) -> AdminStats:
    users = await db.scalar(select(func.count()).select_from(User)) or 0
    records = await db.scalar(select(func.count()).select_from(FortuneRecord)) or 0
    orders = await db.scalar(select(func.count()).select_from(Order)) or 0
    paid_orders = await db.scalar(select(func.count()).select_from(Order).where(Order.status == OrderStatus.paid)) or 0
    notes = await db.scalar(select(func.count()).select_from(VerificationNote)) or 0
    feedback = await db.scalar(select(func.count()).select_from(Feedback)) or 0
    return AdminStats(users=users, records=records, orders=orders, paid_orders=paid_orders, notes=notes, feedback=feedback)


async def users(db: AsyncSession, limit: int, offset: int) -> list[AdminUserItem]:
    rows = (await db.scalars(select(User).order_by(User.created_at.desc()).limit(limit).offset(offset))).all()
    return [AdminUserItem(id=row.id, phone=row.phone, email=row.email, display_name=row.display_name, membership_plan=row.membership_plan.value, membership_status=row.membership_status.value, created_at=row.created_at, last_login_at=row.last_login_at) for row in rows]


async def orders(db: AsyncSession, limit: int, offset: int) -> list[AdminOrderItem]:
    rows = (await db.scalars(select(Order).order_by(Order.created_at.desc()).limit(limit).offset(offset))).all()
    return [AdminOrderItem(id=row.id, user_id=row.user_id, plan=row.plan.value, channel=row.channel.value, status=row.status.value, amount_cents=row.amount_cents, created_at=row.created_at) for row in rows]


async def records(db: AsyncSession, limit: int, offset: int) -> list[AdminRecordItem]:
    rows = (await db.scalars(select(FortuneRecord).order_by(FortuneRecord.cast_at.desc()).limit(limit).offset(offset))).all()
    return [AdminRecordItem(id=row.id, user_id=row.user_id, question=row.question, hexagram_name=row.hexagram_name, changed_hexagram_name=row.changed_hexagram_name, favorite=row.favorite, cast_at=row.cast_at) for row in rows]


async def feedback(
    db: AsyncSession,
    limit: int,
    offset: int,
    query: str | None = None,
    feedback_type: str | None = None,
    feedback_status: str | None = None,
    has_images: bool | None = None,
    starred: bool | None = None,
) -> AdminFeedbackPage:
    conditions = []
    if query:
        keyword = f'%{query.strip()}%'
        conditions.append(
            or_(
                Feedback.description.ilike(keyword),
                User.display_name.ilike(keyword),
                User.email.ilike(keyword),
                User.phone.ilike(keyword),
                Feedback.device_info['email'].astext.ilike(keyword),
                Feedback.device_info['name'].astext.ilike(keyword),
            )
        )
    if feedback_type and feedback_type != 'all':
        conditions.append(Feedback.type == feedback_type)
    if feedback_status and feedback_status != 'all':
        conditions.append(Feedback.status == feedback_status)
    if has_images is True:
        conditions.append(func.jsonb_array_length(Feedback.screenshot_urls) > 0)
    if has_images is False:
        conditions.append(func.jsonb_array_length(Feedback.screenshot_urls) == 0)
    if starred is not None:
        conditions.append(Feedback.starred.is_(starred))

    total = await db.scalar(
        select(func.count())
        .select_from(Feedback)
        .join(User, Feedback.user_id == User.id)
        .where(*conditions)
    ) or 0
    rows = (
        await db.execute(
            select(Feedback, User)
            .join(User, Feedback.user_id == User.id)
            .where(*conditions)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return AdminFeedbackPage(
        items=[_feedback_item(item, user) for item, user in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


async def set_feedback_starred(db: AsyncSession, feedback_id: str, starred: bool, admin_user: User) -> AdminFeedbackItem:
    row = (
        await db.execute(
            select(Feedback, User)
            .join(User, Feedback.user_id == User.id)
            .where(Feedback.id == feedback_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Feedback not found')
    item, user = row
    previous_starred = item.starred
    item.starred = starred
    await write_audit_log(
        db,
        admin_user.id,
        'admin.feedback.star',
        'feedback',
        item.id,
        {'previous_starred': previous_starred, 'starred': starred},
    )
    await db.commit()
    return _feedback_item(item, user)


async def set_feedback_status(db: AsyncSession, feedback_id: str, feedback_status: str, admin_user: User) -> AdminFeedbackItem:
    try:
        next_status = FeedbackStatus(feedback_status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid feedback status') from exc

    row = (
        await db.execute(
            select(Feedback, User)
            .join(User, Feedback.user_id == User.id)
            .where(Feedback.id == feedback_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Feedback not found')
    item, user = row
    previous_status = item.status.value
    item.status = next_status
    await write_audit_log(
        db,
        admin_user.id,
        'admin.feedback.status',
        'feedback',
        item.id,
        {'previous_status': previous_status, 'status': next_status.value},
    )
    await db.commit()
    return _feedback_item(item, user)


async def analytics(db: AsyncSession, days: int) -> AdminAnalytics:
    today = datetime.now(UTC).date()
    start_date = today - timedelta(days=days - 1)
    start_at = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
    labels = [(start_date + timedelta(days=index)).isoformat() for index in range(days)]
    daily = {label: {'users': 0, 'records': 0, 'orders': 0, 'revenue_cents': 0, 'feedback': 0} for label in labels}

    user_rows = await db.execute(
        select(func.date(User.created_at), func.count())
        .where(User.created_at >= start_at)
        .group_by(func.date(User.created_at))
    )
    for day, count in user_rows:
        if str(day) in daily:
            daily[str(day)]['users'] = int(count)

    record_rows = await db.execute(
        select(func.date(FortuneRecord.created_at), func.count())
        .where(FortuneRecord.created_at >= start_at)
        .group_by(func.date(FortuneRecord.created_at))
    )
    for day, count in record_rows:
        if str(day) in daily:
            daily[str(day)]['records'] = int(count)

    order_rows = await db.execute(
        select(func.date(Order.created_at), func.count(), func.coalesce(func.sum(Order.amount_cents), 0))
        .where(Order.created_at >= start_at, Order.status == OrderStatus.paid)
        .group_by(func.date(Order.created_at))
    )
    for day, count, revenue_cents in order_rows:
        if str(day) in daily:
            daily[str(day)]['orders'] = int(count)
            daily[str(day)]['revenue_cents'] = int(revenue_cents)

    feedback_rows = await db.execute(
        select(func.date(Feedback.created_at), func.count())
        .where(Feedback.created_at >= start_at)
        .group_by(func.date(Feedback.created_at))
    )
    for day, count in feedback_rows:
        if str(day) in daily:
            daily[str(day)]['feedback'] = int(count)

    total_revenue = await db.scalar(select(func.coalesce(func.sum(Order.amount_cents), 0)).where(Order.status == OrderStatus.paid)) or 0
    paid_orders = await db.scalar(select(func.count()).select_from(Order).where(Order.status == OrderStatus.paid)) or 0
    pending_orders = await db.scalar(select(func.count()).select_from(Order).where(Order.status == OrderStatus.pending)) or 0
    monthly_revenue = await db.scalar(select(func.coalesce(func.sum(Order.amount_cents), 0)).where(Order.status == OrderStatus.paid, Order.plan == MembershipPlan.monthly)) or 0
    yearly_revenue = await db.scalar(select(func.coalesce(func.sum(Order.amount_cents), 0)).where(Order.status == OrderStatus.paid, Order.plan == MembershipPlan.yearly)) or 0

    return AdminAnalytics(
        daily=[AdminDailyPoint(date=label, **values) for label, values in daily.items()],
        revenue=AdminRevenueSummary(
            total_revenue_cents=int(total_revenue),
            paid_orders=int(paid_orders),
            pending_orders=int(pending_orders),
            monthly_revenue_cents=int(monthly_revenue),
            yearly_revenue_cents=int(yearly_revenue),
        ),
        users=await user_analytics(db),
        feedback=await feedback_analytics(db),
    )


async def user_analytics(db: AsyncSession) -> AdminUserAnalytics:
    real_user_filter = User.is_admin.is_(False)
    now = datetime.now(UTC)
    total_users = await db.scalar(select(func.count()).select_from(User)) or 0
    real_users = await db.scalar(select(func.count()).select_from(User).where(real_user_filter)) or 0
    active_7d_users = await db.scalar(
        select(func.count()).select_from(User).where(real_user_filter, User.last_login_at >= now - timedelta(days=7))
    ) or 0
    active_30d_users = await db.scalar(
        select(func.count()).select_from(User).where(real_user_filter, User.last_login_at >= now - timedelta(days=30))
    ) or 0
    disabled_users = await db.scalar(select(func.count()).select_from(User).where(real_user_filter, User.disabled.is_(True))) or 0
    profile_completed_users = await db.scalar(
        select(func.count()).select_from(User).where(real_user_filter, User.profile_completed.is_(True))
    ) or 0
    total_profiles = (
        await db.scalar(
            select(func.count())
            .select_from(Profile)
            .join(User, Profile.user_id == User.id)
            .where(real_user_filter)
        )
        or 0
    )
    self_profile_users = (
        await db.scalar(
            select(func.count(func.distinct(Profile.user_id)))
            .select_from(Profile)
            .join(User, Profile.user_id == User.id)
            .where(real_user_filter, Profile.relation == '本人')
        )
        or 0
    )
    profile_completion_rate = round((profile_completed_users / real_users) * 100, 1) if real_users else 0
    average_profiles_per_user = round(total_profiles / real_users, 2) if real_users else 0

    return AdminUserAnalytics(
        total_users=int(total_users),
        real_users=int(real_users),
        active_7d_users=int(active_7d_users),
        active_30d_users=int(active_30d_users),
        disabled_users=int(disabled_users),
        profile_completed_users=int(profile_completed_users),
        profile_completion_rate=profile_completion_rate,
        total_profiles=int(total_profiles),
        average_profiles_per_user=average_profiles_per_user,
        self_profile_missing_users=max(int(real_users) - int(self_profile_users), 0),
        login_providers=await _distribution(db, User.register_provider, real_user_filter),
        gender_distribution=await _self_profile_gender_distribution(db),
        membership_plans=await _distribution(db, User.membership_plan, real_user_filter),
        membership_statuses=await _distribution(db, User.membership_status, real_user_filter),
    )


async def _distribution(db: AsyncSession, column, *conditions) -> list[AdminDistributionItem]:
    rows = await db.execute(select(column, func.count()).where(*conditions).group_by(column))
    return [AdminDistributionItem(label=_label(value), count=int(count)) for value, count in rows]


async def feedback_analytics(db: AsyncSession) -> AdminFeedbackAnalytics:
    total_feedback = await db.scalar(select(func.count()).select_from(Feedback)) or 0
    open_feedback = await db.scalar(select(func.count()).select_from(Feedback).where(Feedback.status == FeedbackStatus.open)) or 0
    starred_feedback = await db.scalar(select(func.count()).select_from(Feedback).where(Feedback.starred.is_(True))) or 0
    screenshot_feedback = await db.scalar(
        select(func.count()).select_from(Feedback).where(func.jsonb_array_length(Feedback.screenshot_urls) > 0)
    ) or 0
    return AdminFeedbackAnalytics(
        total_feedback=int(total_feedback),
        open_feedback=int(open_feedback),
        starred_feedback=int(starred_feedback),
        screenshot_feedback=int(screenshot_feedback),
        type_distribution=await _distribution(db, Feedback.type),
        platform_distribution=await _distribution(db, Feedback.platform),
        status_distribution=await _distribution(db, Feedback.status),
    )


async def portal_traffic(db: AsyncSession, days: int) -> AdminPortalTraffic:
    today = datetime.now(UTC).date()
    start_date = today - timedelta(days=days - 1)
    start_at = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    labels = [(start_date + timedelta(days=index)).isoformat() for index in range(days)]
    daily = {label: {'visits': 0, 'unique_visitors': 0, 'sessions': 0} for label in labels}

    daily_rows = await db.execute(
        select(
            func.date(PortalVisit.created_at),
            func.count(),
            func.count(func.distinct(PortalVisit.ip_hash)),
            func.count(func.distinct(PortalVisit.session_id)),
        )
        .where(PortalVisit.created_at >= start_at)
        .group_by(func.date(PortalVisit.created_at))
    )
    for day, visits, unique_visitors, sessions in daily_rows:
        label = str(day)
        if label in daily:
            daily[label] = {
                'visits': int(visits),
                'unique_visitors': int(unique_visitors),
                'sessions': int(sessions),
            }

    total_visits = await db.scalar(select(func.count()).select_from(PortalVisit).where(PortalVisit.created_at >= start_at)) or 0
    unique_visitors = await db.scalar(select(func.count(func.distinct(PortalVisit.ip_hash))).where(PortalVisit.created_at >= start_at)) or 0
    sessions = await db.scalar(select(func.count(func.distinct(PortalVisit.session_id))).where(PortalVisit.created_at >= start_at)) or 0
    today_visits = await db.scalar(select(func.count()).select_from(PortalVisit).where(PortalVisit.created_at >= today_start)) or 0

    return AdminPortalTraffic(
        total_visits=int(total_visits),
        unique_visitors=int(unique_visitors),
        sessions=int(sessions),
        today_visits=int(today_visits),
        daily=[AdminPortalDailyPoint(date=label, **values) for label, values in daily.items()],
        path_distribution=await _top_distribution(db, PortalVisit.path, PortalVisit.created_at >= start_at),
        language_distribution=await _top_distribution(db, PortalVisit.language, PortalVisit.created_at >= start_at),
        referrer_distribution=await _top_distribution(db, PortalVisit.referrer, PortalVisit.created_at >= start_at),
        source_distribution=await _top_distribution(db, PortalVisit.utm_source, PortalVisit.created_at >= start_at),
    )


def _feedback_item(item: Feedback, user: User) -> AdminFeedbackItem:
    device_info = item.device_info or {}
    portal_contact = device_info.get('email') if isinstance(device_info, dict) else None
    return AdminFeedbackItem(
        id=item.id,
        user_id=item.user_id,
        user_display_name=user.display_name,
        user_contact=str(portal_contact) if portal_contact else user.email or user.phone,
        type=item.type.value,
        status=item.status.value,
        starred=item.starred,
        description=item.description,
        screenshot_urls=item.screenshot_urls,
        app_version=item.app_version,
        platform=item.platform,
        created_at=item.created_at,
    )


async def _self_profile_gender_distribution(db: AsyncSession) -> list[AdminDistributionItem]:
    rows = await db.execute(
        select(Profile.gender, func.count())
        .select_from(Profile)
        .join(User, Profile.user_id == User.id)
        .where(User.is_admin.is_(False), Profile.relation == '本人')
        .group_by(Profile.gender)
    )
    return [AdminDistributionItem(label=str(gender or '未填写'), count=int(count)) for gender, count in rows]


async def _top_distribution(db: AsyncSession, column, *conditions, limit: int = 8) -> list[AdminDistributionItem]:
    rows = await db.execute(
        select(column, func.count())
        .where(*conditions)
        .group_by(column)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return [AdminDistributionItem(label=_label(value or 'direct'), count=int(count)) for value, count in rows]


def _label(value) -> str:
    return str(getattr(value, 'value', value))
