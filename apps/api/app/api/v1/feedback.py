from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.feedback import FeedbackCreate, FeedbackOut
from app.services import feedback as service

router = APIRouter(prefix='/feedback', tags=['feedback'])


@router.post('', response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def create_feedback(payload: FeedbackCreate, db: DbSession, user: CurrentUser):
    return await service.create_feedback(db, user, payload)
