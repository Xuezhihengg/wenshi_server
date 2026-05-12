from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.api.deps import CurrentUser, DbSession
from app.schemas.upload import UploadOut
from app.services.uploads import save_avatar_upload, save_feedback_image_upload

router = APIRouter(prefix='/uploads', tags=['uploads'])


@router.post('/avatar', response_model=UploadOut)
async def upload_avatar(user: CurrentUser, db: DbSession, file: Annotated[UploadFile, File()]):
    url = await save_avatar_upload(db, user, file)
    return UploadOut(url=url)


@router.post('/feedback-image', response_model=UploadOut)
async def upload_feedback_image(user: CurrentUser, db: DbSession, file: Annotated[UploadFile, File()]):
    url = await save_feedback_image_upload(db, user, file)
    return UploadOut(url=url)
