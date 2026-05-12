from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.record import (
    AIReadingOut,
    RecordCreate,
    RecordOut,
    RecordUpdate,
    VerificationNoteIn,
    VerificationNoteOut,
    VerificationNoteUpdate,
)
from app.services import records as service

router = APIRouter(prefix='/records', tags=['records'])


@router.get('', response_model=dict)
async def list_records(db: DbSession, user: CurrentUser, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), favorite: bool | None = None, query: str | None = None):
    items, total = await service.list_records(db, user, limit, offset, favorite, query)
    return {'items': [RecordOut.model_validate(item).model_dump(mode='json') for item in items], 'total': total, 'limit': limit, 'offset': offset}


@router.post('', response_model=RecordOut, status_code=status.HTTP_201_CREATED)
async def save_record(payload: RecordCreate, db: DbSession, user: CurrentUser):
    return await service.upsert_record(db, user, payload)


@router.get('/{record_id}', response_model=RecordOut)
async def get_record(record_id: str, db: DbSession, user: CurrentUser):
    return await service.get_record(db, user, record_id)


@router.post('/{record_id}/ai-reading', response_model=AIReadingOut)
async def generate_ai_reading(record_id: str, db: DbSession, user: CurrentUser, lang: str = Query('zh', pattern='^(zh|en)$')):
    return await service.generate_ai_reading(db, user, record_id, lang=lang)


@router.patch('/{record_id}', response_model=RecordOut)
async def update_record(record_id: str, payload: RecordUpdate, db: DbSession, user: CurrentUser):
    return await service.update_record(db, user, record_id, payload)


@router.post('/{record_id}/favorite', response_model=RecordOut)
async def toggle_favorite(record_id: str, db: DbSession, user: CurrentUser):
    return await service.toggle_favorite(db, user, record_id)


@router.post('/{record_id}/notes', response_model=VerificationNoteOut, status_code=status.HTTP_201_CREATED)
async def create_note(record_id: str, payload: VerificationNoteIn, db: DbSession, user: CurrentUser):
    return await service.create_note(db, user, record_id, payload)


@router.patch('/{record_id}/notes/{note_id}', response_model=VerificationNoteOut)
async def update_note(record_id: str, note_id: str, payload: VerificationNoteUpdate, db: DbSession, user: CurrentUser):
    return await service.update_note(db, user, record_id, note_id, payload)


@router.delete('/{record_id}/notes/{note_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(record_id: str, note_id: str, db: DbSession, user: CurrentUser):
    await service.delete_note(db, user, record_id, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
