import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps' / 'api'))

from app.db.session import AsyncSessionLocal
from app.models import (
    AuditLog,
    AuthProvider,
    FortuneRecord,
    MembershipPlan,
    MembershipStatus,
    NotificationSetting,
    Order,
    OrderChannel,
    OrderStatus,
    Profile,
    User,
    VerificationNote,
)

SEED_EMAILS = [
    'chenxi@example.com',
    'linan@example.com',
    'muyun@example.com',
]


def now() -> datetime:
    return datetime.now(UTC)


def record_payload(question: str, base: str, changed: str | None, profile_name: str) -> dict:
    return {
        'source': 'dev-seed',
        'question': question,
        'profile': {'name': profile_name},
        'castTime': now().isoformat(),
        'hexagram': {
            'base': base,
            'changed': changed,
            'lines': ['阳', '阴', '阴', '阳', '阳', '阴'],
            'movingLines': [2, 5] if changed else [],
        },
        'useGod': {'role': '妻财', 'line': '三爻', 'element': '木'},
        'notes': 'Mock payload for local admin and API development.',
    }


async def clear_seed_data(session):
    seed_users = (await session.scalars(select(User).where(User.email.in_(SEED_EMAILS)))).all()
    seed_user_ids = [user.id for user in seed_users]
    if not seed_user_ids:
        return
    await session.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_(seed_user_ids)))
    await session.execute(delete(User).where(User.id.in_(seed_user_ids)))
    await session.commit()


async def create_user(session, *, phone, email, name, provider, plan, status, expires_days=None, is_admin=False):
    user = User(
        phone=phone,
        email=email,
        display_name=name,
        register_provider=provider,
        membership_plan=plan,
        membership_status=status,
        membership_expires_at=now() + timedelta(days=expires_days) if expires_days else None,
        last_login_at=now() - timedelta(hours=2),
        is_admin=is_admin,
    )
    session.add(user)
    await session.flush()
    session.add(
        NotificationSetting(
            user_id=user.id,
            system_enabled=True,
            push_enabled=status == MembershipStatus.active,
            daily_check_in=True,
            reading_complete=True,
            quiet_hours_enabled=True,
            quiet_start='22:30',
            quiet_end='08:00',
        )
    )
    return user


async def add_profile(session, user, *, name, relation, gender, birthday, selected=False):
    profile = Profile(user_id=user.id, name=name, relation=relation, gender=gender, birthday=birthday, is_selected=selected)
    session.add(profile)
    await session.flush()
    return profile


async def add_record(session, user, profile, *, question, base, changed=None, favorite=False, days_ago=0, note=None, fulfilled=True):
    cast_at = now() - timedelta(days=days_ago, hours=days_ago % 4)
    record = FortuneRecord(
        user_id=user.id,
        profile_id=profile.id,
        question=question,
        hexagram_name=base,
        changed_hexagram_name=changed,
        favorite=favorite,
        cast_at=cast_at,
        payload=record_payload(question, base, changed, profile.name),
        ai_reading_status='not_requested',
    )
    session.add(record)
    await session.flush()
    if note is not None:
        session.add(
            VerificationNote(
                record_id=record.id,
                fulfilled=fulfilled,
                note=note,
                noted_at=cast_at + timedelta(days=1, hours=3),
            )
        )
    return record


async def add_order(session, user, *, plan, channel, status, amount, days_ago=0):
    paid_at = now() - timedelta(days=days_ago) if status == OrderStatus.paid else None
    order = Order(
        user_id=user.id,
        plan=plan,
        channel=channel,
        status=status,
        amount_cents=amount,
        currency='CNY',
        provider_order_id=f'seed-{uuid4()}',
        raw_payload={'source': 'dev-seed', 'channel': channel.value},
        paid_at=paid_at,
    )
    session.add(order)
    return order


async def main():
    async with AsyncSessionLocal() as session:
        await clear_seed_data(session)

        chen = await create_user(
            session,
            phone='13800000001',
            email='chenxi@example.com',
            name='陈溪',
            provider=AuthProvider.phone,
            plan=MembershipPlan.monthly,
            status=MembershipStatus.active,
            expires_days=23,
        )
        chen_self = await add_profile(session, chen, name='陈溪', relation='本人', gender='女', birthday='1994-03-18 申时', selected=True)
        chen_mom = await add_profile(session, chen, name='母亲', relation='家人', gender='女', birthday='1968-09-02 卯时')
        await add_record(session, chen, chen_self, question='这个项目本月能推进吗', base='地风升', changed='水风井', favorite=True, days_ago=0, note='会议后对方明确给出排期，初步应验。', fulfilled=True)
        await add_record(session, chen, chen_mom, question='母亲近期身体恢复如何', base='山雷颐', changed=None, favorite=False, days_ago=3, note='复查指标稳定，仍需观察。', fulfilled=True)
        await add_order(session, chen, plan=MembershipPlan.monthly, channel=OrderChannel.apple, status=OrderStatus.paid, amount=1800, days_ago=5)

        lin = await create_user(
            session,
            phone='13800000002',
            email='linan@example.com',
            name='林安',
            provider=AuthProvider.email,
            plan=MembershipPlan.trial,
            status=MembershipStatus.trial,
        )
        lin_self = await add_profile(session, lin, name='林安', relation='本人', gender='男', birthday='1991-11-07 子时', selected=True)
        await add_record(session, lin, lin_self, question='这次考试是否顺利', base='火天大有', changed='雷天大壮', favorite=False, days_ago=1, note='成绩未达预期，结果未应验。', fulfilled=False)
        await add_record(session, lin, lin_self, question='近期财运有没有起色', base='风火家人', changed=None, favorite=True, days_ago=9)
        await add_order(session, lin, plan=MembershipPlan.yearly, channel=OrderChannel.mock, status=OrderStatus.pending, amount=18800, days_ago=0)

        mu = await create_user(
            session,
            phone='13800000003',
            email='muyun@example.com',
            name='穆云',
            provider=AuthProvider.apple,
            plan=MembershipPlan.yearly,
            status=MembershipStatus.active,
            expires_days=310,
        )
        mu_self = await add_profile(session, mu, name='穆云', relation='本人', gender='其他', birthday='1988-06-21 午时', selected=True)
        mu_partner = await add_profile(session, mu, name='伴侣', relation='伴侣', gender='女', birthday='1990-02-14 巳时')
        await add_record(session, mu, mu_partner, question='对方现在真实想法是什么', base='泽山咸', changed='泽火革', favorite=True, days_ago=2, note='沟通后态度明显缓和。', fulfilled=True)
        await add_record(session, mu, mu_self, question='是否适合今年换城市发展', base='水山蹇', changed='地山谦', favorite=False, days_ago=15)
        await add_order(session, mu, plan=MembershipPlan.yearly, channel=OrderChannel.alipay, status=OrderStatus.paid, amount=18800, days_ago=40)

        session.add(AuditLog(actor_user_id=chen.id, action='seed.create_demo_data', target_type='system', target_id='dev', metadata_json={'users': 3}))
        await session.commit()

    print('Seeded 3 users, 6 profiles, 6 fortune records, 4 notes, 3 orders.')


if __name__ == '__main__':
    asyncio.run(main())
