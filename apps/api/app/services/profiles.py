from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile, User
from app.schemas.profile import ProfileCreate, ProfileUpdate


async def list_profiles(db: AsyncSession, user: User) -> list[Profile]:
    return list((await db.scalars(select(Profile).where(Profile.user_id == user.id).order_by(Profile.created_at))).all())


async def get_self_profile(db: AsyncSession, user: User) -> Profile | None:
    return await db.scalar(select(Profile).where(Profile.user_id == user.id, Profile.relation == '本人').order_by(Profile.created_at))


async def create_profile(db: AsyncSession, user: User, payload: ProfileCreate) -> Profile:
    if payload.is_selected:
        await db.execute(update(Profile).where(Profile.user_id == user.id).values(is_selected=False))
    profile = Profile(user_id=user.id, **payload.model_dump())
    db.add(profile)
    update_user_profile_completed(user, profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def get_profile_for_user(db: AsyncSession, user: User, profile_id: str) -> Profile:
    profile = await db.get(Profile, profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Profile not found')
    return profile


async def update_profile(db: AsyncSession, user: User, profile_id: str, payload: ProfileUpdate) -> Profile:
    profile = await get_profile_for_user(db, user, profile_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get('is_selected'):
        await db.execute(update(Profile).where(Profile.user_id == user.id).values(is_selected=False))
    for key, value in data.items():
        setattr(profile, key, value)
    update_user_profile_completed(user, profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def select_profile(db: AsyncSession, user: User, profile_id: str) -> Profile:
    profile = await get_profile_for_user(db, user, profile_id)
    await db.execute(update(Profile).where(Profile.user_id == user.id).values(is_selected=False))
    profile.is_selected = True
    await db.commit()
    await db.refresh(profile)
    return profile


async def delete_profile(db: AsyncSession, user: User, profile_id: str) -> None:
    profile = await get_profile_for_user(db, user, profile_id)
    if profile.relation == '本人':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Self profile cannot be deleted')
    await db.delete(profile)
    await db.commit()


def update_user_profile_completed(user: User, profile: Profile) -> None:
    if profile.relation != '本人':
        return
    user.profile_completed = (
        profile.name.strip() not in {'', '本人', '未命名用户'}
        and profile.gender in {'男', '女'}
        and profile.birthday.strip() not in {'', '未填写'}
    )


async def refresh_user_profile_completed(db: AsyncSession, user: User) -> bool:
    self_profile = await get_self_profile(db, user)
    if not self_profile:
        user.profile_completed = False
    else:
        update_user_profile_completed(user, self_profile)
    await db.commit()
    return user.profile_completed
