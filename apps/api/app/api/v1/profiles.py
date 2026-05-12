from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.profile import ProfileCreate, ProfileOut, ProfileUpdate
from app.services import profiles as service

router = APIRouter(prefix='/profiles', tags=['profiles'])


@router.get('', response_model=list[ProfileOut])
async def list_profiles(db: DbSession, user: CurrentUser):
    return await service.list_profiles(db, user)


@router.post('', response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
async def create_profile(payload: ProfileCreate, db: DbSession, user: CurrentUser):
    return await service.create_profile(db, user, payload)


@router.patch('/{profile_id}', response_model=ProfileOut)
async def update_profile(profile_id: str, payload: ProfileUpdate, db: DbSession, user: CurrentUser):
    return await service.update_profile(db, user, profile_id, payload)


@router.post('/{profile_id}/select', response_model=ProfileOut)
async def select_profile(profile_id: str, db: DbSession, user: CurrentUser):
    return await service.select_profile(db, user, profile_id)


@router.delete('/{profile_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: str, db: DbSession, user: CurrentUser):
    await service.delete_profile(db, user, profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
